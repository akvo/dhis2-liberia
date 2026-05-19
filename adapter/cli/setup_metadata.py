#!/usr/bin/env python
"""
DHIS2 Org Unit Metadata Setup

Sets up the required metadata for org unit-based facility sync:
1. Create SUNBIRD_OSID organisation unit attribute
2. Create Org Unit Groups (BOREHOLE, HAND_PUMP, etc.)
3. Create Org Unit Group Set (optional)

Usage:
    python -m adapter.cli.setup_metadata
    python -m adapter.cli.setup_metadata --skip-groups
"""

import argparse
import os
import sys
from pathlib import Path

import requests


# =============================================================================
# Load .env
# =============================================================================


def load_env():
    """Load environment variables from .env file."""
    env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())


load_env()

# =============================================================================
# Configuration
# =============================================================================

BASE_URL = os.environ.get("DHIS2_URL", "http://localhost:9090/api")
AUTH = (
    os.environ.get("DHIS2_USERNAME", "admin"),
    os.environ.get("DHIS2_PASSWORD", "district"),
)
HEADERS = {"Content-Type": "application/json", "Accept": "application/json"}

# Org Unit Attribute for Sunbird OSID
OSID_ATTRIBUTE = {
    "name": "Sunbird OSID",
    "shortName": "OSID",
    "code": "SUNBIRD_OSID",
    "valueType": "TEXT",
    "organisationUnitAttribute": True,
}

# Org Unit Groups for facility types
ORG_UNIT_GROUPS = [
    {"name": "Borehole", "shortName": "Borehole", "code": "BOREHOLE"},
    {"name": "Hand Pump", "shortName": "Hand Pump", "code": "HAND_PUMP"},
    {"name": "Protected Well", "shortName": "Protected Well", "code": "PROTECTED_WELL"},
    {"name": "Unprotected Well", "shortName": "Unprotected Well", "code": "UNPROTECTED_WELL"},
    {"name": "Protected Spring", "shortName": "Protected Spring", "code": "PROTECTED_SPRING"},
    {"name": "Unprotected Spring", "shortName": "Unprotected Spring", "code": "UNPROTECTED_SPRING"},
    {"name": "Piped Water", "shortName": "Piped Water", "code": "PIPED_WATER"},
    {"name": "Rainwater Harvesting", "shortName": "Rainwater", "code": "RAINWATER_HARVESTING"},
]

# Org Unit Group Set (optional, for categorization)
ORG_UNIT_GROUP_SET = {
    "name": "Water Facility Type",
    "shortName": "WF Type",
    "code": "WATER_FACILITY_TYPE",
    "dataDimension": True,
    "compulsory": False,
}

# Store created IDs
created_attribute_id = None
created_group_ids = {}
created_group_set_id = None


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


def dhis2_put(endpoint, data):
    """PUT request to DHIS2 API."""
    return requests.put(
        f"{BASE_URL}/{endpoint}", auth=AUTH, headers=HEADERS, json=data
    )


# =============================================================================
# Setup Functions
# =============================================================================


def check_connection():
    """Check DHIS2 connection."""
    print("=" * 60)
    print("DHIS2 Org Unit Metadata Setup")
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


def create_osid_attribute():
    """Create SUNBIRD_OSID organisation unit attribute."""
    global created_attribute_id

    print("\n1. Creating SUNBIRD_OSID Attribute...")

    # Check if exists
    response = dhis2_get(
        f"attributes?filter=code:eq:{OSID_ATTRIBUTE['code']}&fields=id,name,code"
    )
    if response.status_code == 200:
        attrs = response.json().get("attributes", [])
        if attrs:
            created_attribute_id = attrs[0]["id"]
            print(f"   Exists: {OSID_ATTRIBUTE['name']} (ID: {created_attribute_id})")
            return True

    # Create attribute
    response = dhis2_post("metadata", {"attributes": [OSID_ATTRIBUTE]})

    if response.status_code in [200, 201]:
        result = response.json()
        if result.get("status") == "OK":
            # Fetch created ID
            get_response = dhis2_get(
                f"attributes?filter=code:eq:{OSID_ATTRIBUTE['code']}&fields=id"
            )
            if get_response.status_code == 200:
                attrs = get_response.json().get("attributes", [])
                if attrs:
                    created_attribute_id = attrs[0]["id"]
                    print(f"   Created: {OSID_ATTRIBUTE['name']} (ID: {created_attribute_id})")
                    return True

    print(f"   FAILED: {response.text[:200]}")
    return False


def create_org_unit_groups():
    """Create org unit groups for facility types."""
    global created_group_ids

    print("\n2. Creating Org Unit Groups...")

    # Check existing groups
    codes = [g["code"] for g in ORG_UNIT_GROUPS]
    response = dhis2_get(
        f"organisationUnitGroups?filter=code:in:[{','.join(codes)}]&fields=id,name,code"
    )
    if response.status_code == 200:
        for group in response.json().get("organisationUnitGroups", []):
            created_group_ids[group["code"]] = group["id"]
            print(f"   Exists: {group['name']}")

    # Create missing groups
    groups_to_create = []
    for group in ORG_UNIT_GROUPS:
        if group["code"] not in created_group_ids:
            groups_to_create.append(group)

    if groups_to_create:
        response = dhis2_post("metadata", {"organisationUnitGroups": groups_to_create})

        if response.status_code in [200, 201]:
            result = response.json()
            if result.get("status") == "OK":
                # Fetch created IDs
                codes = [g["code"] for g in groups_to_create]
                get_response = dhis2_get(
                    f"organisationUnitGroups?filter=code:in:[{','.join(codes)}]&fields=id,name,code"
                )
                if get_response.status_code == 200:
                    for group in get_response.json().get("organisationUnitGroups", []):
                        created_group_ids[group["code"]] = group["id"]
                        print(f"   Created: {group['name']}")
            else:
                print(f"   FAILED: {result}")
        else:
            print(f"   FAILED: {response.text[:200]}")

    print(f"   Total: {len(created_group_ids)} org unit groups")
    return len(created_group_ids) > 0


def create_org_unit_group_set():
    """Create org unit group set (optional)."""
    global created_group_set_id

    print("\n3. Creating Org Unit Group Set...")

    # Check if exists
    response = dhis2_get(
        f"organisationUnitGroupSets?filter=code:eq:{ORG_UNIT_GROUP_SET['code']}&fields=id,name,code"
    )
    if response.status_code == 200:
        group_sets = response.json().get("organisationUnitGroupSets", [])
        if group_sets:
            created_group_set_id = group_sets[0]["id"]
            print(f"   Exists: {ORG_UNIT_GROUP_SET['name']} (ID: {created_group_set_id})")
            return True

    # Create group set with references to groups
    group_set_payload = {
        **ORG_UNIT_GROUP_SET,
        "organisationUnitGroups": [
            {"id": gid} for gid in created_group_ids.values()
        ]
    }

    response = dhis2_post("metadata", {"organisationUnitGroupSets": [group_set_payload]})

    if response.status_code in [200, 201]:
        result = response.json()
        if result.get("status") == "OK":
            # Fetch created ID
            get_response = dhis2_get(
                f"organisationUnitGroupSets?filter=code:eq:{ORG_UNIT_GROUP_SET['code']}&fields=id"
            )
            if get_response.status_code == 200:
                group_sets = get_response.json().get("organisationUnitGroupSets", [])
                if group_sets:
                    created_group_set_id = group_sets[0]["id"]
                    print(f"   Created: {ORG_UNIT_GROUP_SET['name']} (ID: {created_group_set_id})")
                    return True

    print(f"   FAILED: {response.text[:200]}")
    return False


def print_summary():
    """Print setup summary."""
    print("\n" + "=" * 60)
    print("Setup Summary")
    print("=" * 60)
    print(f"  SUNBIRD_OSID Attribute: {'Yes' if created_attribute_id else 'No'}")
    print(f"  Org Unit Groups: {len(created_group_ids)}")
    for code, gid in created_group_ids.items():
        print(f"    - {code}: {gid}")
    print(f"  Group Set: {'Yes' if created_group_set_id else 'No'}")
    print("\nNext steps:")
    print("  1. Import admin hierarchy: python -m adapter.cli.setup_admin_hierarchy")
    print("  2. Create facilities: python -m adapter.cli.create_facility")


# =============================================================================
# Main
# =============================================================================


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="DHIS2 Org Unit Metadata Setup")
    parser.add_argument(
        "--skip-groups", action="store_true",
        help="Skip org unit group creation"
    )
    parser.add_argument(
        "--skip-group-set", action="store_true",
        help="Skip org unit group set creation"
    )
    args = parser.parse_args()

    if not check_connection():
        sys.exit(1)

    create_osid_attribute()

    if not args.skip_groups:
        create_org_unit_groups()

        if not args.skip_group_set and created_group_ids:
            create_org_unit_group_set()

    print_summary()


if __name__ == "__main__":
    main()
