#!/usr/bin/env python
"""
Create a test Water Facility TEI in DHIS2 with syncStatus=PENDING.
Run this to create test data, then run sync.py to sync.
"""

import os
import time
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

# Configuration (from environment variables)
BASE_URL = os.environ.get("DHIS2_URL", "http://localhost:9090/api")
AUTH = (
    os.environ.get("DHIS2_USERNAME", "admin"),
    os.environ.get("DHIS2_PASSWORD", "district"),
)
HEADERS = {"Content-Type": "application/json", "Accept": "application/json"}

# These will be populated at runtime
PROGRAM_ID = None
TE_TYPE_ID = None
TEST_OU_ID = None
ATTR_IDS = {}
COUNTY_OU_ID = None
DISTRICT_OU_ID = None
COMMUNITY_OU_ID = None


def fetch_dhis2_ids():
    """Fetch DHIS2 IDs dynamically by code."""
    global PROGRAM_ID, TE_TYPE_ID, TEST_OU_ID, ATTR_IDS
    global COUNTY_OU_ID, DISTRICT_OU_ID, COMMUNITY_OU_ID

    # Fetch program by code
    response = requests.get(
        f"{BASE_URL}/programs?filter=code:eq:WF_REGISTRY&fields=id,name",
        auth=AUTH,
        headers=HEADERS,
    )
    if response.status_code != 200:
        raise Exception(f"Failed to fetch program: {response.status_code}")
    programs = response.json().get("programs", [])
    if not programs:
        raise Exception("Program WF_REGISTRY not found. Run dhis2-water-facility-setup.ipynb first.")
    PROGRAM_ID = programs[0]["id"]

    # Fetch tracked entity type by code
    response = requests.get(
        f"{BASE_URL}/trackedEntityTypes?filter=code:eq:WATER_FACILITY&fields=id,name",
        auth=AUTH,
        headers=HEADERS,
    )
    if response.status_code != 200:
        raise Exception(f"Failed to fetch TE type: {response.status_code}")
    te_types = response.json().get("trackedEntityTypes", [])
    if not te_types:
        raise Exception("Tracked Entity Type WATER_FACILITY not found.")
    TE_TYPE_ID = te_types[0]["id"]

    # Fetch tracked entity attributes by codes
    attr_codes = [
        "GEO_CODE", "COUNTY", "DISTRICT", "COMMUNITY",
        "WATER_POINT_TYPE_ATTR", "SYNC_STATUS_ATTR",
        "EXTRACTION_TYPE_ATTR", "PUMP_TYPE_ATTR", "INSTALLER", "OWNER"
    ]
    codes_param = ",".join(attr_codes)
    response = requests.get(
        f"{BASE_URL}/trackedEntityAttributes?filter=code:in:[{codes_param}]&fields=id,code&paging=false",
        auth=AUTH,
        headers=HEADERS,
    )
    if response.status_code != 200:
        raise Exception(f"Failed to fetch attributes: {response.status_code}")
    attributes = response.json().get("trackedEntityAttributes", [])
    ATTR_IDS = {attr["code"]: attr["id"] for attr in attributes}

    # Fetch org units by code
    ou_codes = ["LR_MON", "LR_MON_GM", "LR_MON_GM_CT"]
    codes_param = ",".join(ou_codes)
    response = requests.get(
        f"{BASE_URL}/organisationUnits?filter=code:in:[{codes_param}]&fields=id,code&paging=false",
        auth=AUTH,
        headers=HEADERS,
    )
    if response.status_code != 200:
        raise Exception(f"Failed to fetch org units: {response.status_code}")
    org_units = response.json().get("organisationUnits", [])
    ou_map = {ou["code"]: ou["id"] for ou in org_units}

    COUNTY_OU_ID = ou_map.get("LR_MON")
    DISTRICT_OU_ID = ou_map.get("LR_MON_GM")
    COMMUNITY_OU_ID = ou_map.get("LR_MON_GM_CT")
    TEST_OU_ID = COMMUNITY_OU_ID

    if not all([COUNTY_OU_ID, DISTRICT_OU_ID, COMMUNITY_OU_ID]):
        raise Exception("Required org units not found. Run dhis2-water-facility-setup.ipynb first.")

    print(f"  Program: {PROGRAM_ID}")
    print(f"  TE Type: {TE_TYPE_ID}")
    print(f"  Test OU: {TEST_OU_ID}")
    print(f"  Attributes: {len(ATTR_IDS)} loaded")


def create_water_facility():
    """Create a new Water Facility TEI with syncStatus=PENDING."""
    # Generate unique geo code
    geo_code = f"WF{int(time.time())}"
    today = datetime.now().strftime("%Y-%m-%d")

    # Build attributes
    attributes = [
        {"attribute": ATTR_IDS["GEO_CODE"], "value": geo_code},
        {"attribute": ATTR_IDS["COUNTY"], "value": COUNTY_OU_ID},
        {"attribute": ATTR_IDS["DISTRICT"], "value": DISTRICT_OU_ID},
        {"attribute": ATTR_IDS["COMMUNITY"], "value": COMMUNITY_OU_ID},
        {"attribute": ATTR_IDS["WATER_POINT_TYPE_ATTR"], "value": "WATER_POINT_TYPE_PDW"},
        {"attribute": ATTR_IDS["SYNC_STATUS_ATTR"], "value": "SYNC_STATUS_PENDING"},
        {"attribute": ATTR_IDS["EXTRACTION_TYPE_ATTR"], "value": "EXTRACTION_TYPE_SOLAR"},
        {"attribute": ATTR_IDS["PUMP_TYPE_ATTR"], "value": "PUMP_TYPE_AFRIDEV"},
        {"attribute": ATTR_IDS["INSTALLER"], "value": "INSTALLER_TYPE_GOVERNMENT"},
        {"attribute": ATTR_IDS["OWNER"], "value": "OWNER_TYPE_SCHOOL"},
    ]

    # Create TEI with enrollment
    payload = {
        "trackedEntityType": TE_TYPE_ID,
        "orgUnit": TEST_OU_ID,
        "attributes": attributes,
        "geometry": {
            "type": "Point",
            "coordinates": [-10.8123, 6.2987]
        },
        "enrollments": [
            {
                "orgUnit": TEST_OU_ID,
                "program": PROGRAM_ID,
                "enrollmentDate": today,
                "incidentDate": today
            }
        ]
    }

    response = requests.post(
        f"{BASE_URL}/trackedEntityInstances",
        auth=AUTH,
        headers=HEADERS,
        json=payload
    )

    if response.status_code in [200, 201]:
        result = response.json()
        if result.get("response", {}).get("status") == "SUCCESS":
            tei_id = result["response"]["importSummaries"][0]["reference"]
            print("Created new Water Facility:")
            print(f"  TEI ID: {tei_id}")
            print(f"  GEO_CODE: {geo_code}")
            print(f"  Water Point Type: Protected dug well")
            print(f"  Extraction Type: Solar")
            print(f"  Pump Type: Afridev")
            print(f"  Installer: Government")
            print(f"  Owner: School")
            print(f"  syncStatus: PENDING")
            print()
            print("Now run: python adapter/sync.py")
            return tei_id
        else:
            print(f"Failed: {result}")
    else:
        print(f"Error: {response.status_code}")
        print(response.text)
    return None


if __name__ == "__main__":
    print("Fetching DHIS2 metadata...")
    try:
        fetch_dhis2_ids()
    except Exception as e:
        print(f"FAILED: {e}")
        exit(1)
    print()
    create_water_facility()
