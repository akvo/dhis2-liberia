#!/usr/bin/env python
"""
DHIS2 to Sunbird RC Integration Adapter

Syncs Water Facility records from DHIS2 to Sunbird RC:
1. Fetches TEIs with syncStatus=PENDING from DHIS2
2. Resolves org unit UIDs to names
3. Transforms to Sunbird RC format
4. POSTs to Sunbird RC
5. Updates DHIS2 with osid, wfId, syncStatus=SYNCED
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import requests


# =============================================================================
# Load .env file (from project root)
# =============================================================================


def load_env():
    """Load environment variables from .env file."""
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())


load_env()


# =============================================================================
# Load config from JSON file
# =============================================================================


def load_config():
    """Load configuration from config.json."""
    config_path = Path(__file__).parent / "config.json"
    if not config_path.exists():
        raise Exception(f"Config file not found: {config_path}")
    with open(config_path) as f:
        return json.load(f)


CONFIG = load_config()

# =============================================================================
# Configuration (from environment variables)
# =============================================================================

DHIS2_URL = os.environ.get("DHIS2_URL", "http://localhost:9090/api")
DHIS2_AUTH = (
    os.environ.get("DHIS2_USERNAME", "admin"),
    os.environ.get("DHIS2_PASSWORD", "district"),
)

SUNBIRD_URL = os.environ.get("SUNBIRD_URL", "http://localhost:8081/api/v1")
KEYCLOAK_URL = os.environ.get(
    "KEYCLOAK_URL",
    "http://keycloak:8080/auth/realms/sunbird-rc/protocol/openid-connect/token"
)
CLIENT_ID = os.environ.get("SUNBIRD_CLIENT_ID", "demo-api")
CLIENT_SECRET = os.environ.get("SUNBIRD_CLIENT_SECRET", "")

# =============================================================================
# Configuration (from config.json)
# =============================================================================

# Build attribute codes list from attributes
ATTR_CODES_LIST = [attr["code"] for attr in CONFIG["attributes"]]


# Build option mappings from option_sets
# Maps attribute code -> {full_option_code: display_name}
def build_option_mappings():
    """Build option mappings for adapter from config option_sets."""
    mappings = {}
    # Create lookup: option_set_code -> attribute_code
    attr_to_option_set = {}
    for attr in CONFIG["attributes"]:
        if "optionSetCode" in attr:
            attr_to_option_set[attr["optionSetCode"]] = attr["code"]

    for option_set in CONFIG["option_sets"]:
        os_code = option_set["code"]
        attr_code = attr_to_option_set.get(os_code)
        if attr_code:
            mappings[attr_code] = {}
            for opt in option_set["options"]:
                full_code = f"{os_code}_{opt['code']}"
                mappings[attr_code][full_code] = opt["name"]
    return mappings


FIELD_MAPPING = CONFIG["field_mapping"]
OPTION_MAPPINGS = build_option_mappings()
ORG_UNIT_FIELDS = CONFIG["org_unit_fields"]
SYNC_STATUS = CONFIG["sync_status"]

# These will be populated at runtime
ROOT_OU_ID = None
PROGRAM_ID = None
ATTR_IDS = {}
ATTR_CODES = {}

# Cache for org unit names
ORG_UNIT_CACHE = {}


# =============================================================================
# DHIS2 ID Fetching (Dynamic)
# =============================================================================


def fetch_dhis2_ids():
    """Fetch DHIS2 IDs dynamically by code. Must be called before sync."""
    global ROOT_OU_ID, PROGRAM_ID, ATTR_IDS, ATTR_CODES

    headers = {"Accept": "application/json"}

    # Fetch root org unit (level 1)
    response = requests.get(
        f"{DHIS2_URL}/organisationUnits"
        f"?filter=level:eq:1&fields=id,name&paging=false",
        auth=DHIS2_AUTH,
        headers=headers,
    )
    if response.status_code != 200:
        raise Exception(
            f"Failed to fetch root org unit: {response.status_code}"
        )
    org_units = response.json().get("organisationUnits", [])
    if not org_units:
        raise Exception("No root organisation unit found")
    ROOT_OU_ID = org_units[0]["id"]

    # Fetch program by code
    prog_code = CONFIG["program"]["code"]
    response = requests.get(
        f"{DHIS2_URL}/programs"
        f"?filter=code:eq:{prog_code}&fields=id,name&paging=false",
        auth=DHIS2_AUTH,
        headers=headers,
    )
    if response.status_code != 200:
        raise Exception(f"Failed to fetch program: {response.status_code}")
    programs = response.json().get("programs", [])
    if not programs:
        raise Exception(
            f"Program {prog_code} not found. "
            "Run setup.py first."
        )
    PROGRAM_ID = programs[0]["id"]

    # Fetch tracked entity attributes by codes
    codes_param = ",".join(ATTR_CODES_LIST)
    response = requests.get(
        f"{DHIS2_URL}/trackedEntityAttributes"
        f"?filter=code:in:[{codes_param}]&fields=id,code&paging=false",
        auth=DHIS2_AUTH,
        headers=headers,
    )
    if response.status_code != 200:
        raise Exception(f"Failed to fetch attributes: {response.status_code}")
    attributes = response.json().get("trackedEntityAttributes", [])

    ATTR_IDS = {attr["code"]: attr["id"] for attr in attributes}
    ATTR_CODES = {v: k for k, v in ATTR_IDS.items()}

    # Verify all required attributes exist
    missing = [code for code in ATTR_CODES_LIST if code not in ATTR_IDS]
    if missing:
        raise Exception(
            f"Missing attributes: {missing}. Run setup.py first."
        )

    return True


# =============================================================================
# DHIS2 API Functions
# =============================================================================


def dhis2_get(endpoint):
    """GET request to DHIS2 API."""
    url = f"{DHIS2_URL}/{endpoint}"
    response = requests.get(
        url, auth=DHIS2_AUTH, headers={"Accept": "application/json"}
    )
    return response


def dhis2_put(endpoint, data):
    """PUT request to DHIS2 API."""
    url = f"{DHIS2_URL}/{endpoint}"
    response = requests.put(
        url,
        auth=DHIS2_AUTH,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json"
        },
        json=data,
    )
    return response


def resolve_org_unit(uid):
    """Convert org unit UID to name."""
    if not uid:
        return None
    if uid in ORG_UNIT_CACHE:
        return ORG_UNIT_CACHE[uid]

    response = dhis2_get(f"organisationUnits/{uid}?fields=name")
    if response.status_code == 200:
        name = response.json().get("name")
        ORG_UNIT_CACHE[uid] = name
        return name
    return None


def get_attribute_value(tei, attr_code):
    """Extract attribute value from TEI by attribute code."""
    attr_id = ATTR_IDS.get(attr_code)
    if not attr_id:
        return None
    for attr in tei.get("attributes", []):
        if attr.get("attribute") == attr_id:
            return attr.get("value")
    return None


def option_code_to_name(code, attr_code):
    """Convert DHIS2 option code to display name using config."""
    if not code:
        return None
    option_map = OPTION_MAPPINGS.get(attr_code, {})
    return option_map.get(code, code)


# =============================================================================
# Sunbird RC API Functions
# =============================================================================


def get_sunbird_token():
    """Get OAuth2 access token from Keycloak."""
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "client_credentials",
    }
    response = requests.post(KEYCLOAK_URL, data=data)
    if response.status_code == 200:
        return response.json().get("access_token")
    raise Exception(
        f"Failed to get Sunbird token: {response.status_code} {response.text}"
    )


def sunbird_post(endpoint, data, token):
    """POST request to Sunbird RC API."""
    url = f"{SUNBIRD_URL}/{endpoint}"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }
    response = requests.post(url, headers=headers, json=data)
    return response


def sunbird_get(endpoint, token):
    """GET request to Sunbird RC API."""
    url = f"{SUNBIRD_URL}/{endpoint}"
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
    }
    response = requests.get(url, headers=headers)
    return response


# =============================================================================
# Sync Functions
# =============================================================================


def fetch_pending_teis():
    """Fetch TEIs with syncStatus=PENDING from DHIS2."""
    sync_status_id = ATTR_IDS["SYNC_STATUS_ATTR"]
    pending_status = SYNC_STATUS["pending"]
    endpoint = (
        f"trackedEntityInstances"
        f"?ou={ROOT_OU_ID}"
        f"&ouMode=DESCENDANTS"
        f"&program={PROGRAM_ID}"
        f"&filter={sync_status_id}:eq:{pending_status}"
        f"&fields=*"
        f"&paging=false"
    )
    response = dhis2_get(endpoint)
    if response.status_code != 200:
        raise Exception(
            f"Failed to fetch TEIs: {response.status_code} {response.text}"
        )

    data = response.json()
    teis = data.get("trackedEntityInstances", [])
    return teis


def transform_tei_to_sunbird(tei):
    """Transform DHIS2 TEI to Sunbird RC WaterFacility format."""
    # Get basic fields
    geo_code = get_attribute_value(tei, "GEO_CODE")

    # Resolve org unit UIDs to names
    county_uid = get_attribute_value(tei, "COUNTY")
    district_uid = get_attribute_value(tei, "DISTRICT")
    community_uid = get_attribute_value(tei, "COMMUNITY")

    county_name = resolve_org_unit(county_uid)
    district_name = resolve_org_unit(district_uid)
    community_name = resolve_org_unit(community_uid)

    # Get coordinates from TEI geometry
    geometry = tei.get("geometry")
    coordinates = None
    if geometry and geometry.get("type") == "Point":
        coords = geometry.get("coordinates", [])
        if len(coords) >= 2:
            # DHIS2 stores as [lon, lat]
            coordinates = {"lat": coords[1], "lon": coords[0]}

    # Map option codes to display names (using config)
    water_point_type = option_code_to_name(
        get_attribute_value(tei, "WATER_POINT_TYPE_ATTR"),
        "WATER_POINT_TYPE_ATTR"
    )
    extraction_type = option_code_to_name(
        get_attribute_value(tei, "EXTRACTION_TYPE_ATTR"),
        "EXTRACTION_TYPE_ATTR"
    )
    pump_type = option_code_to_name(
        get_attribute_value(tei, "PUMP_TYPE_ATTR"),
        "PUMP_TYPE_ATTR"
    )
    installer = option_code_to_name(
        get_attribute_value(tei, "INSTALLER"),
        "INSTALLER"
    )
    owner = option_code_to_name(
        get_attribute_value(tei, "OWNER"),
        "OWNER"
    )

    # Get other fields
    num_taps = get_attribute_value(tei, "NUM_TAPS")
    has_depth_info = get_attribute_value(tei, "HAS_DEPTH_INFO")
    depth_metres = get_attribute_value(tei, "DEPTH_METRES")
    funder = get_attribute_value(tei, "FUNDER")
    photo_url = get_attribute_value(tei, "PHOTO_URL")

    # Build Sunbird RC payload
    sunbird_data = {
        "geoCode": geo_code,
        "waterPointType": water_point_type,
        "location": {
            "county": county_name,
            "district": district_name,
            "community": community_name,
        },
    }

    # Add coordinates if available
    if coordinates:
        sunbird_data["location"]["coordinates"] = coordinates

    # Add optional fields if present
    if extraction_type:
        sunbird_data["extractionType"] = extraction_type
    if pump_type:
        sunbird_data["pumpType"] = pump_type
    if installer:
        sunbird_data["installer"] = installer
    if owner:
        sunbird_data["owner"] = owner
    if num_taps:
        sunbird_data["numTaps"] = int(num_taps)
    if has_depth_info is not None:
        sunbird_data["hasDepthInfo"] = has_depth_info == "true"
    if depth_metres:
        sunbird_data["depthMetres"] = float(depth_metres)
    if funder:
        sunbird_data["funder"] = funder
    if photo_url:
        sunbird_data["photoUrl"] = photo_url

    return sunbird_data


def update_tei_with_ids(tei_id, osid, wf_id, org_unit_id):
    """Update DHIS2 TEI with Sunbird RC generated IDs."""
    synced_status = SYNC_STATUS["synced"]
    attributes = [
        {"attribute": ATTR_IDS["SUNBIRD_OSID"], "value": osid},
        {"attribute": ATTR_IDS["WF_ID"], "value": wf_id},
        {"attribute": ATTR_IDS["SYNC_STATUS_ATTR"], "value": synced_status},
    ]

    payload = {"orgUnit": org_unit_id, "attributes": attributes}

    response = dhis2_put(f"trackedEntityInstances/{tei_id}", payload)
    return response.status_code in [200, 204]


def set_tei_failed(tei_id, org_unit_id):
    """Set TEI syncStatus to FAILED."""
    attributes = [
        {
            "attribute": ATTR_IDS["SYNC_STATUS_ATTR"],
            "value": SYNC_STATUS["failed"]
        },
    ]

    payload = {"orgUnit": org_unit_id, "attributes": attributes}

    dhis2_put(f"trackedEntityInstances/{tei_id}", payload)


def sync_tei(tei, token):
    """Sync a single TEI to Sunbird RC."""
    tei_id = tei.get("trackedEntityInstance")
    org_unit_id = tei.get("orgUnit")
    geo_code = get_attribute_value(tei, "GEO_CODE")

    print(f"  Syncing TEI {tei_id} (geoCode: {geo_code})...")

    # Transform to Sunbird RC format
    sunbird_data = transform_tei_to_sunbird(tei)

    # POST to Sunbird RC
    response = sunbird_post("WaterFacility", sunbird_data, token)

    if response.status_code not in [200, 201]:
        print(f"    FAILED: Sunbird RC create failed: {response.status_code}")
        print(f"    Response: {response.text}")
        set_tei_failed(tei_id, org_unit_id)
        return False

    # Extract osid from response
    result = response.json()
    osid = result.get("result", {}).get("WaterFacility", {}).get("osid")

    if not osid:
        print("    FAILED: No osid in response")
        set_tei_failed(tei_id, org_unit_id)
        return False

    # GET the created record to fetch wfId
    get_response = sunbird_get(f"WaterFacility/{osid}", token)

    if get_response.status_code != 200:
        print(
            f"    FAILED: Could not fetch record: {get_response.status_code}"
        )
        set_tei_failed(tei_id, org_unit_id)
        return False

    facility = get_response.json()
    wf_id = facility.get("wfId")

    if not wf_id:
        print("    WARNING: No wfId in Sunbird RC response")
        wf_id = ""  # Use empty string if not generated

    # Update DHIS2 with IDs
    if update_tei_with_ids(tei_id, osid, wf_id, org_unit_id):
        print(f"    SUCCESS: osid={osid}, wfId={wf_id}")
        return True
    else:
        print("    FAILED: Could not update DHIS2")
        return False


def run_sync():
    """Main sync function."""
    print("=" * 60)
    print("DHIS2 -> Sunbird RC Sync")
    print("Started:", datetime.now().isoformat())
    print("=" * 60)

    # Fetch DHIS2 IDs dynamically
    print("\n1. Fetching DHIS2 metadata...")
    try:
        fetch_dhis2_ids()
        print(f"   Root OU: {ROOT_OU_ID}")
        print(f"   Program: {PROGRAM_ID}")
        print(f"   Attributes: {len(ATTR_IDS)} loaded")
    except Exception as e:
        print(f"   FAILED: {e}")
        return

    # Get Sunbird RC token
    print("\n2. Authenticating with Sunbird RC...")
    try:
        token = get_sunbird_token()
        print("   Token acquired successfully")
    except Exception as e:
        print(f"   FAILED: {e}")
        return

    # Fetch pending TEIs
    print("\n3. Fetching pending TEIs from DHIS2...")
    try:
        teis = fetch_pending_teis()
        print(f"   Found {len(teis)} pending records")
    except Exception as e:
        print(f"   FAILED: {e}")
        return

    if not teis:
        print("\n   No pending records to sync.")
        return

    # Sync each TEI
    print("\n4. Syncing records...")
    success_count = 0
    fail_count = 0

    for tei in teis:
        if sync_tei(tei, token):
            success_count += 1
        else:
            fail_count += 1

    # Summary
    print("\n" + "=" * 60)
    print("Sync Summary")
    print("=" * 60)
    print(f"  Total processed: {len(teis)}")
    print(f"  Successful: {success_count}")
    print(f"  Failed: {fail_count}")
    print("Finished:", datetime.now().isoformat())


# =============================================================================
# Test Functions
# =============================================================================


def test_dhis2():
    """Test DHIS2 connection."""
    print("Testing DHIS2 connection...")
    response = dhis2_get("system/info")
    if response.status_code == 200:
        info = response.json()
        print(f"  Connected to DHIS2 version {info.get('version')}")

        # Fetch IDs dynamically
        print("\nFetching DHIS2 metadata...")
        try:
            fetch_dhis2_ids()
            print(f"  Root OU: {ROOT_OU_ID}")
            print(f"  Program: {PROGRAM_ID}")
            print(f"  Attributes: {len(ATTR_IDS)} loaded")
        except Exception as e:
            print(f"  FAILED: {e}")
            return False

        # Test fetching pending TEIs
        print("\nTesting pending TEI fetch...")
        teis = fetch_pending_teis()
        print(f"  Found {len(teis)} pending TEIs")

        # Show first TEI details if any
        if teis:
            tei = teis[0]
            print("\n  Sample TEI:")
            print(f"    ID: {tei.get('trackedEntityInstance')}")
            print(f"    GeoCode: {get_attribute_value(tei, 'GEO_CODE')}")
            print(f"    County UID: {get_attribute_value(tei, 'COUNTY')}")
            county_name = resolve_org_unit(get_attribute_value(tei, "COUNTY"))
            print(f"    County Name: {county_name}")
        return True
    else:
        print(f"  Failed: {response.status_code}")
        print(f"  {response.text}")
        return False


def test_sunbird():
    """Test Sunbird RC connection."""
    print("Testing Sunbird RC connection...")
    try:
        token = get_sunbird_token()
        print("  Token acquired successfully")

        # Test API access
        response = sunbird_get("WaterFacility", token)
        print(f"  WaterFacility API status: {response.status_code}")
        return True
    except Exception as e:
        print(f"  Failed: {e}")
        return False


# =============================================================================
# Main
# =============================================================================


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="DHIS2 to Sunbird RC sync adapter"
    )
    parser.add_argument(
        "--test-dhis2", action="store_true", help="Test DHIS2 connection"
    )
    parser.add_argument(
        "--test-sunbird", action="store_true", help="Test Sunbird RC connection"
    )

    args = parser.parse_args()

    if args.test_dhis2:
        sys.exit(0 if test_dhis2() else 1)
    elif args.test_sunbird:
        sys.exit(0 if test_sunbird() else 1)
    else:
        run_sync()
