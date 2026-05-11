#!/usr/bin/env python
"""
Create a test Water Facility TEI in DHIS2 with syncStatus=PENDING.
Run this to create test data, then run sync.py to sync.

Usage:
    python adapter/create_facility.py
    python adapter/create_facility.py --count 5
"""

import argparse
import json
import os
import random
import time
from datetime import datetime
from pathlib import Path

import requests


# =============================================================================
# Load .env and config
# =============================================================================


def load_env():
    """Load environment variables from .env file."""
    # .env is in project root (three levels up from cli/)
    env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())


def load_config():
    """Load configuration from setup_config.json."""
    # Config is in adapter/ (one level up from cli/)
    config_path = Path(__file__).parent.parent / "setup_config.json"
    if not config_path.exists():
        raise Exception(f"Config file not found: {config_path}")
    with open(config_path) as f:
        return json.load(f)


load_env()
CONFIG = load_config()

# Configuration
BASE_URL = os.environ.get("DHIS2_URL", "http://localhost:9090/api")
AUTH = (
    os.environ.get("DHIS2_USERNAME", "admin"),
    os.environ.get("DHIS2_PASSWORD", "district"),
)
HEADERS = {"Content-Type": "application/json", "Accept": "application/json"}

# Will be populated at runtime
PROGRAM_ID = None
TE_TYPE_ID = None
ATTR_IDS = {}
ORG_UNITS = {}


# =============================================================================
# Build option code lookup from config
# =============================================================================


def build_option_codes():
    """Build lookup: option_set_code -> list of full option codes."""
    options = {}
    for option_set in CONFIG["option_sets"]:
        os_code = option_set["code"]
        options[os_code] = [
            f"{os_code}_{opt['code']}" for opt in option_set["options"]
        ]
    return options


OPTION_CODES = build_option_codes()


def get_random_option(option_set_code):
    """Get a random option code for the given option set."""
    codes = OPTION_CODES.get(option_set_code, [])
    return random.choice(codes) if codes else None


# =============================================================================
# Fetch DHIS2 IDs
# =============================================================================


def fetch_dhis2_ids():
    """Fetch DHIS2 IDs dynamically by code."""
    global PROGRAM_ID, TE_TYPE_ID, ATTR_IDS, ORG_UNITS

    # Fetch program
    prog_code = CONFIG['program']['code']
    response = requests.get(
        f"{BASE_URL}/programs?filter=code:eq:{prog_code}&fields=id,name",
        auth=AUTH, headers=HEADERS
    )
    if response.status_code != 200:
        raise Exception(f"Failed to fetch program: {response.status_code}")
    programs = response.json().get("programs", [])
    if not programs:
        raise Exception("Program not found. Run setup.py first.")
    PROGRAM_ID = programs[0]["id"]

    # Fetch tracked entity type
    te_code = CONFIG['tracked_entity_type']['code']
    response = requests.get(
        f"{BASE_URL}/trackedEntityTypes?filter=code:eq:{te_code}&fields=id",
        auth=AUTH, headers=HEADERS
    )
    if response.status_code != 200:
        raise Exception(f"Failed to fetch TE type: {response.status_code}")
    te_types = response.json().get("trackedEntityTypes", [])
    if not te_types:
        raise Exception("Tracked Entity Type not found. Run setup.py first.")
    TE_TYPE_ID = te_types[0]["id"]

    # Fetch attributes
    attr_codes = [attr["code"] for attr in CONFIG["attributes"]]
    codes_param = ",".join(attr_codes)
    response = requests.get(
        f"{BASE_URL}/trackedEntityAttributes"
        f"?filter=code:in:[{codes_param}]&fields=id,code&paging=false",
        auth=AUTH, headers=HEADERS
    )
    if response.status_code != 200:
        raise Exception(f"Failed to fetch attributes: {response.status_code}")
    attributes = response.json().get("trackedEntityAttributes", [])
    ATTR_IDS = {attr["code"]: attr["id"] for attr in attributes}

    # Fetch org units
    ou_codes = [
        "LR_MON", "LR_MON_GM", "LR_MON_GM_CT", "LR_MON_GM_PV",
        "LR_NIM", "LR_NIM_SM", "LR_NIM_SM_SQ"
    ]
    codes_param = ",".join(ou_codes)
    response = requests.get(
        f"{BASE_URL}/organisationUnits"
        f"?filter=code:in:[{codes_param}]&fields=id,code,name&paging=false",
        auth=AUTH, headers=HEADERS
    )
    if response.status_code != 200:
        raise Exception(f"Failed to fetch org units: {response.status_code}")
    org_units = response.json().get("organisationUnits", [])
    ORG_UNITS = {
        ou["code"]: {"id": ou["id"], "name": ou["name"]}
        for ou in org_units
    }

    print(f"  Program: {PROGRAM_ID}")
    print(f"  TE Type: {TE_TYPE_ID}")
    print(f"  Attributes: {len(ATTR_IDS)}")
    print(f"  Org Units: {len(ORG_UNITS)}")


# =============================================================================
# Create facility
# =============================================================================


def create_water_facility():
    """Create a new Water Facility TEI with random values."""
    geo_code = f"WF{int(time.time())}{random.randint(100, 999)}"
    today = datetime.now().strftime("%Y-%m-%d")

    # Pick random location (county/district/community sets)
    location_sets = [
        ("LR_MON", "LR_MON_GM", "LR_MON_GM_CT"),
        ("LR_MON", "LR_MON_GM", "LR_MON_GM_PV"),
    ]
    # Add Nimba if available
    nimba_available = (
        "LR_NIM" in ORG_UNITS
        and "LR_NIM_SM" in ORG_UNITS
        and "LR_NIM_SM_SQ" in ORG_UNITS
    )
    if nimba_available:
        location_sets.append(("LR_NIM", "LR_NIM_SM", "LR_NIM_SM_SQ"))

    county_code, district_code, community_code = random.choice(location_sets)

    county_ou = ORG_UNITS.get(county_code, {})
    district_ou = ORG_UNITS.get(district_code, {})
    community_ou = ORG_UNITS.get(community_code, {})

    if not community_ou:
        print("  ERROR: Community org unit not found")
        return None

    # Build attributes from config
    attributes = [
        {"attribute": ATTR_IDS["GEO_CODE"], "value": geo_code},
        {"attribute": ATTR_IDS["COUNTY"], "value": county_ou["id"]},
        {"attribute": ATTR_IDS["DISTRICT"], "value": district_ou["id"]},
        {"attribute": ATTR_IDS["COMMUNITY"], "value": community_ou["id"]},
    ]

    # Add option-based attributes with random values
    for attr in CONFIG["attributes"]:
        if "optionSetCode" in attr and attr["code"] in ATTR_IDS:
            option_code = get_random_option(attr["optionSetCode"])
            if option_code:
                # For sync status, always use PENDING
                if attr["optionSetCode"] == "SYNC_STATUS":
                    option_code = "SYNC_STATUS_PENDING"
                attributes.append({
                    "attribute": ATTR_IDS[attr["code"]],
                    "value": option_code
                })

    # Random coordinates around Liberia
    lon = round(-10.5 + random.uniform(-0.5, 0.5), 4)
    lat = round(6.3 + random.uniform(-0.3, 0.3), 4)

    payload = {
        "trackedEntityType": TE_TYPE_ID,
        "orgUnit": community_ou["id"],
        "attributes": attributes,
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
        "enrollments": [{
            "orgUnit": community_ou["id"],
            "program": PROGRAM_ID,
            "enrollmentDate": today,
            "incidentDate": today
        }]
    }

    response = requests.post(
        f"{BASE_URL}/trackedEntityInstances",
        auth=AUTH, headers=HEADERS, json=payload
    )

    if response.status_code in [200, 201]:
        result = response.json()
        if result.get("response", {}).get("status") == "SUCCESS":
            tei_id = result["response"]["importSummaries"][0]["reference"]

            # Get the created attribute values for display
            water_type_id = ATTR_IDS.get("WATER_POINT_TYPE_ATTR")
            extraction_id = ATTR_IDS.get("EXTRACTION_TYPE_ATTR")
            water_type = next(
                (a["value"] for a in attributes
                 if a["attribute"] == water_type_id), ""
            )
            extraction = next(
                (a["value"] for a in attributes
                 if a["attribute"] == extraction_id), ""
            )

            print(f"  Created: {geo_code}")
            print(f"    TEI ID: {tei_id}")
            print(f"    Location: {community_ou.get('name', community_code)}")
            print(f"    Water Type: {water_type}")
            print(f"    Extraction: {extraction}")
            return tei_id
        else:
            print(f"  FAILED: {result}")
    else:
        print(f"  ERROR: {response.status_code}")
        print(f"  {response.text[:300]}")
    return None


# =============================================================================
# Main
# =============================================================================


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Create test Water Facility")
    parser.add_argument(
        "--count", type=int, default=1,
        help="Number of facilities to create"
    )
    args = parser.parse_args()

    print("Fetching DHIS2 metadata...")
    try:
        fetch_dhis2_ids()
    except Exception as e:
        print(f"FAILED: {e}")
        exit(1)

    print(f"\nCreating {args.count} Water Facility(ies)...")
    created = 0
    for i in range(args.count):
        if create_water_facility():
            created += 1

    print(f"\nCreated: {created}/{args.count}")
    print("Run: python adapter/sync.py")


if __name__ == "__main__":
    main()
