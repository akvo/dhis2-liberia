#!/usr/bin/env python
"""
DHIS2 Water Facility Setup

Sets up the Water Facility Tracked Entity in DHIS2:
1. Create Option Sets
2. Create Tracked Entity Attributes
3. Create Tracked Entity Type
4. Create Tracker Program
5. Import Organisation Units
6. Assign user to org units

Usage:
    python adapter/setup.py
    python adapter/setup.py --skip-org-units
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests


# =============================================================================
# Load .env and config
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


def load_config():
    """Load configuration from config.json."""
    config_path = Path(__file__).parent / "config.json"
    if not config_path.exists():
        raise Exception(f"Config file not found: {config_path}")
    with open(config_path) as f:
        return json.load(f)


load_env()
CONFIG = load_config()

# =============================================================================
# Configuration
# =============================================================================

BASE_URL = os.environ.get("DHIS2_URL", "http://localhost:9090/api")
AUTH = (
    os.environ.get("DHIS2_USERNAME", "admin"),
    os.environ.get("DHIS2_PASSWORD", "district"),
)
HEADERS = {"Content-Type": "application/json", "Accept": "application/json"}

# Will be populated during setup
created_option_sets = {}
created_attributes = {}
created_org_units = {}
te_type_id = None
program_id = None


# =============================================================================
# API Helpers
# =============================================================================


def dhis2_get(endpoint):
    """GET request to DHIS2 API."""
    return requests.get(f"{BASE_URL}/{endpoint}", auth=AUTH, headers=HEADERS)


def dhis2_post(endpoint, data):
    """POST request to DHIS2 API."""
    return requests.post(
        f"{BASE_URL}/{endpoint}", auth=AUTH, headers=HEADERS, json=data
    )


# =============================================================================
# Setup Functions
# =============================================================================


def check_connection():
    """Check DHIS2 connection."""
    print("=" * 60)
    print("DHIS2 Water Facility Setup")
    print("=" * 60)
    print(f"\nConnecting to {BASE_URL}...")

    response = dhis2_get("system/info")
    if response.status_code == 200:
        info = response.json()
        print(f"  DHIS2 Version: {info.get('version')}")
        print(f"  Database: {info.get('databaseInfo', {}).get('name')}")
        return True
    else:
        print(f"  FAILED: {response.status_code}")
        return False


def create_option_sets():
    """Create option sets from config."""
    global created_option_sets

    print("\n1. Creating Option Sets...")

    # Check existing
    codes = [os_item["code"] for os_item in CONFIG["option_sets"]]
    response = dhis2_get(
        f"optionSets?filter=code:in:[{','.join(codes)}]&fields=id,name,code"
    )
    if response.status_code == 200:
        for os_item in response.json().get("optionSets", []):
            created_option_sets[os_item["code"]] = os_item["id"]
            print(f"   Exists: {os_item['name']}")

    # Create missing
    for option_set in CONFIG["option_sets"]:
        if option_set["code"] in created_option_sets:
            continue

        os_code = option_set["code"]

        # Create option set
        os_payload = {
            "name": option_set["name"],
            "code": os_code,
            "valueType": "TEXT"
        }
        response = dhis2_post("metadata", {"optionSets": [os_payload]})

        if response.status_code not in [200, 201]:
            print(f"   FAILED: {option_set['name']}")
            continue
        if response.json().get("status") != "OK":
            print(f"   FAILED: {option_set['name']}")
            continue

        # Get created ID
        get_response = dhis2_get(
            f"optionSets?filter=code:eq:{os_code}&fields=id"
        )
        if get_response.status_code != 200:
            continue
        os_data = get_response.json()
        if not os_data.get("optionSets"):
            continue
        os_id = os_data["optionSets"][0]["id"]
        created_option_sets[os_code] = os_id

        # Create options
        options_payload = []
        for i, opt in enumerate(option_set["options"]):
            opt_code = f"{os_code}_{opt['code']}"
            options_payload.append({
                "name": opt["name"],
                "code": opt_code,
                "sortOrder": i + 1,
                "optionSet": {"id": os_id}
            })

        response = dhis2_post("metadata", {"options": options_payload})
        if response.status_code in [200, 201]:
            if response.json().get("status") == "OK":
                print(
                    f"   Created: {option_set['name']} "
                    f"({len(options_payload)} options)"
                )
            else:
                print(f"   FAILED options: {option_set['name']}")
        else:
            print(f"   FAILED options: {option_set['name']}")

    print(f"   Total: {len(created_option_sets)} option sets")


def create_attributes():
    """Create tracked entity attributes from config."""
    global created_attributes

    print("\n2. Creating Tracked Entity Attributes...")

    # Check existing
    codes = [attr["code"] for attr in CONFIG["attributes"]]
    response = dhis2_get(
        f"trackedEntityAttributes?filter=code:in:[{','.join(codes)}]"
        f"&fields=id,name,code&paging=false"
    )
    if response.status_code == 200:
        for attr in response.json().get("trackedEntityAttributes", []):
            attr_def = next(
                (a for a in CONFIG["attributes"] if a["code"] == attr["code"]),
                {}
            )
            created_attributes[attr["code"]] = {
                "id": attr["id"],
                "name": attr["name"],
                "searchable": attr_def.get("searchable", False)
            }
            print(f"   Exists: {attr['name']}")

    # Create missing
    for attr in CONFIG["attributes"]:
        if attr["code"] in created_attributes:
            continue

        payload = {
            "name": attr["name"],
            "shortName": attr["shortName"],
            "code": attr["code"],
            "valueType": attr["valueType"],
            "aggregationType": attr["aggregationType"]
        }

        if attr.get("unique"):
            payload["unique"] = True

        # Link to option set
        os_code = attr.get("optionSetCode")
        if os_code and os_code in created_option_sets:
            payload["optionSet"] = {"id": created_option_sets[os_code]}

        response = dhis2_post(
            "metadata", {"trackedEntityAttributes": [payload]}
        )

        if response.status_code in [200, 201]:
            if response.json().get("status") == "OK":
                get_response = dhis2_get(
                    f"trackedEntityAttributes?filter=code:eq:{attr['code']}"
                    f"&fields=id,name,code"
                )
                if get_response.status_code == 200:
                    attr_data = get_response.json()
                    if attr_data.get("trackedEntityAttributes"):
                        attr_id = attr_data["trackedEntityAttributes"][0]["id"]
                        created_attributes[attr["code"]] = {
                            "id": attr_id,
                            "name": attr["name"],
                            "searchable": attr.get("searchable", False)
                        }
                        print(f"   Created: {attr['name']}")
            else:
                print(f"   FAILED: {attr['name']}")
        else:
            print(f"   FAILED: {attr['name']}")

    print(f"   Total: {len(created_attributes)} attributes")


def create_tracked_entity_type():
    """Create tracked entity type."""
    global te_type_id

    print("\n3. Creating Tracked Entity Type...")

    te_config = CONFIG["tracked_entity_type"]
    response = dhis2_get(
        f"trackedEntityTypes?filter=code:eq:{te_config['code']}"
        f"&fields=id,name,code"
    )

    resp_ok = response.status_code == 200
    if resp_ok and response.json().get("trackedEntityTypes"):
        te_type_id = response.json()["trackedEntityTypes"][0]["id"]
        print(f"   Exists: {te_config['name']} (ID: {te_type_id})")
        return

    # Build attributes list
    te_type_attributes = []
    display_attrs = [
        "SUNBIRD_OSID", "WF_ID", "SYNC_STATUS_ATTR", "GEO_CODE",
        "COUNTY", "DISTRICT", "COMMUNITY", "WATER_POINT_TYPE_ATTR"
    ]

    for i, (code, attr_info) in enumerate(created_attributes.items()):
        te_type_attributes.append({
            "trackedEntityAttribute": {"id": attr_info["id"]},
            "displayInList": code in display_attrs,
            "searchable": attr_info.get("searchable", False),
            "sortOrder": i + 1
        })

    payload = {
        "name": te_config["name"],
        "shortName": te_config["shortName"],
        "code": te_config["code"],
        "description": "Water facilities with Sunbird RC integration",
        "featureType": "POINT",
        "trackedEntityTypeAttributes": te_type_attributes
    }

    response = dhis2_post("metadata", {"trackedEntityTypes": [payload]})

    if response.status_code in [200, 201]:
        if response.json().get("status") == "OK":
            get_response = dhis2_get(
                f"trackedEntityTypes?filter=code:eq:{te_config['code']}"
                f"&fields=id"
            )
            if get_response.status_code == 200:
                type_data = get_response.json()
                if type_data.get("trackedEntityTypes"):
                    te_type_id = type_data["trackedEntityTypes"][0]["id"]
                    print(
                        f"   Created: {te_config['name']} (ID: {te_type_id})"
                    )
        else:
            print(f"   FAILED: {response.text[:200]}")
    else:
        print(f"   FAILED: {response.text[:200]}")


def create_org_units():
    """Create organisation units from CSV."""
    global created_org_units

    print("\n4. Creating Organisation Units...")

    csv_path = Path(__file__).parent.parent / "org_units_sample.csv"
    if not csv_path.exists():
        print(f"   SKIPPED: {csv_path} not found")
        return

    org_df = pd.read_csv(csv_path)
    org_df_sorted = org_df.sort_values('level')

    for _, row in org_df_sorted.iterrows():
        # Check if exists
        response = dhis2_get(
            f"organisationUnits?filter=code:eq:{row['code']}"
            f"&fields=id,name,code"
        )
        if response.status_code == 200:
            if response.json().get("organisationUnits"):
                existing = response.json()["organisationUnits"][0]
                created_org_units[row['code']] = existing['id']
                indent = "  " * (int(row['level']) - 1)
                print(f"   {indent}Exists: {row['name']}")
                continue

        # Determine parent
        parent_id = None
        if pd.notna(row.get('parent_code')) and row['parent_code']:
            parent_id = created_org_units.get(row['parent_code'])

        org_unit = {
            "name": row['name'],
            "shortName": row['short_name'],
            "code": row['code'],
            "openingDate": "2020-01-01"
        }
        if parent_id:
            org_unit["parent"] = {"id": parent_id}

        response = dhis2_post("metadata", {"organisationUnits": [org_unit]})

        if response.status_code in [200, 201]:
            if response.json().get("status") == "OK":
                get_response = dhis2_get(
                    f"organisationUnits?filter=code:eq:{row['code']}&fields=id"
                )
                if get_response.status_code == 200:
                    ou_data = get_response.json()
                    if ou_data.get("organisationUnits"):
                        ou_id = ou_data["organisationUnits"][0]["id"]
                        created_org_units[row['code']] = ou_id
                        indent = "  " * (int(row['level']) - 1)
                        print(f"   {indent}Created: {row['name']}")

    print(f"   Total: {len(created_org_units)} org units")


def assign_user_to_org_units():
    """Assign admin user to root org unit."""
    print("\n5. Assigning User to Org Units...")

    root_ou_id = created_org_units.get("LR")
    if not root_ou_id:
        print("   SKIPPED: No root org unit")
        return

    response = dhis2_get("me?fields=id,organisationUnits")
    if response.status_code != 200:
        print("   FAILED: Could not get user")
        return

    user_data = response.json()
    user_id = user_data.get("id")

    # Check if already assigned
    current_ous = user_data.get("organisationUnits", [])
    if any(ou.get("id") == root_ou_id for ou in current_ous):
        print("   Already assigned")
        return

    # Assign to org units
    success = 0
    endpoints = [
        "organisationUnits",
        "dataViewOrganisationUnits",
        "teiSearchOrganisationUnits"
    ]
    for endpoint in endpoints:
        response = requests.post(
            f"{BASE_URL}/users/{user_id}/{endpoint}/{root_ou_id}",
            auth=AUTH, headers=HEADERS
        )
        if response.status_code in [200, 201, 204]:
            success += 1

    print(f"   Assigned ({success}/3)")


def create_program():
    """Create tracker program."""
    global program_id

    print("\n6. Creating Tracker Program...")

    prog_config = CONFIG["program"]
    response = dhis2_get(
        f"programs?filter=code:eq:{prog_config['code']}&fields=id,name,code"
    )

    if response.status_code == 200 and response.json().get("programs"):
        program_id = response.json()["programs"][0]["id"]
        print(f"   Exists: {prog_config['name']} (ID: {program_id})")
        return

    # Get all org units for program
    response = dhis2_get("organisationUnits?fields=id&paging=false")
    all_org_units = []
    if response.status_code == 200:
        all_org_units = [
            {"id": ou["id"]}
            for ou in response.json().get("organisationUnits", [])
        ]

    # Build program attributes
    mandatory_attrs = [
        "GEO_CODE", "COUNTY", "DISTRICT", "COMMUNITY", "WATER_POINT_TYPE_ATTR"
    ]
    display_attrs = [
        "SUNBIRD_OSID", "WF_ID", "SYNC_STATUS_ATTR", "GEO_CODE",
        "COUNTY", "DISTRICT", "WATER_POINT_TYPE_ATTR"
    ]

    program_attributes = []
    for i, (code, attr_info) in enumerate(created_attributes.items()):
        program_attributes.append({
            "trackedEntityAttribute": {"id": attr_info["id"]},
            "displayInList": code in display_attrs,
            "mandatory": code in mandatory_attrs,
            "searchable": attr_info.get("searchable", False),
            "sortOrder": i + 1
        })

    payload = {
        "name": prog_config["name"],
        "shortName": prog_config["shortName"],
        "code": prog_config["code"],
        "programType": "WITH_REGISTRATION",
        "trackedEntityType": {"id": te_type_id},
        "displayFrontPageList": True,
        "featureType": "POINT",
        "onlyEnrollOnce": True,
        "programTrackedEntityAttributes": program_attributes,
        "organisationUnits": all_org_units
    }

    response = dhis2_post("metadata", {"programs": [payload]})

    if response.status_code in [200, 201]:
        if response.json().get("status") == "OK":
            get_response = dhis2_get(
                f"programs?filter=code:eq:{prog_config['code']}&fields=id"
            )
            if get_response.status_code == 200:
                prog_data = get_response.json()
                if prog_data.get("programs"):
                    program_id = prog_data["programs"][0]["id"]
                    print(
                        f"   Created: {prog_config['name']} (ID: {program_id})"
                    )
        else:
            print(f"   FAILED: {response.text[:200]}")
    else:
        print(f"   FAILED: {response.text[:200]}")


def create_test_facility():
    """Create a test water facility."""
    print("\n7. Creating Test Water Facility...")

    if not all([te_type_id, program_id, created_org_units]):
        print("   SKIPPED: Missing prerequisites")
        return

    test_ou_id = created_org_units.get("LR_MON_GM_CT")
    if not test_ou_id:
        print("   SKIPPED: Test org unit not found")
        return

    geo_code = f"TEST{int(time.time())}"
    today = datetime.now().strftime("%Y-%m-%d")

    attributes = [
        {"attribute": created_attributes["GEO_CODE"]["id"], "value": geo_code},
        {
            "attribute": created_attributes["COUNTY"]["id"],
            "value": created_org_units.get("LR_MON")
        },
        {
            "attribute": created_attributes["DISTRICT"]["id"],
            "value": created_org_units.get("LR_MON_GM")
        },
        {
            "attribute": created_attributes["COMMUNITY"]["id"],
            "value": test_ou_id
        },
        {
            "attribute": created_attributes["WATER_POINT_TYPE_ATTR"]["id"],
            "value": "WATER_POINT_TYPE_TWB"
        },
        {
            "attribute": created_attributes["SYNC_STATUS_ATTR"]["id"],
            "value": "SYNC_STATUS_PENDING"
        },
    ]

    payload = {
        "trackedEntityType": te_type_id,
        "orgUnit": test_ou_id,
        "attributes": attributes,
        "geometry": {"type": "Point", "coordinates": [-10.7957, 6.3156]},
        "enrollments": [{
            "orgUnit": test_ou_id,
            "program": program_id,
            "enrollmentDate": today,
            "incidentDate": today
        }]
    }

    response = dhis2_post("trackedEntityInstances", payload)

    if response.status_code in [200, 201]:
        result = response.json()
        if result.get("response", {}).get("status") == "SUCCESS":
            tei_id = result["response"]["importSummaries"][0]["reference"]
            print(f"   Created: {geo_code} (TEI: {tei_id})")
            return

    print(f"   FAILED: {response.text[:200]}")


def print_summary():
    """Print setup summary."""
    print("\n" + "=" * 60)
    print("Setup Summary")
    print("=" * 60)
    print(f"  Option Sets: {len(created_option_sets)}")
    print(f"  Attributes: {len(created_attributes)}")
    print(f"  Tracked Entity Type: {'Yes' if te_type_id else 'No'}")
    print(f"  Program: {'Yes' if program_id else 'No'}")
    print(f"  Org Units: {len(created_org_units)}")
    print("\nSetup complete!")
    tracker_url = "http://localhost:9090/dhis-web-tracker-capture/"
    print(f"  - Tracker Capture: {tracker_url}")
    print("  - Run sync: python adapter/sync.py")


# =============================================================================
# Main
# =============================================================================


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="DHIS2 Water Facility Setup")
    parser.add_argument(
        "--skip-org-units", action="store_true",
        help="Skip org unit creation"
    )
    parser.add_argument(
        "--skip-test", action="store_true",
        help="Skip test facility creation"
    )
    args = parser.parse_args()

    if not check_connection():
        sys.exit(1)

    create_option_sets()
    create_attributes()
    create_tracked_entity_type()

    if not args.skip_org_units:
        create_org_units()
        assign_user_to_org_units()

    create_program()

    if not args.skip_test:
        create_test_facility()

    print_summary()


if __name__ == "__main__":
    main()
