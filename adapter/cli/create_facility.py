#!/usr/bin/env python
"""
Create Facility Org Unit

Creates a single facility as an organisation unit and assigns it to a group.

Usage:
    python -m adapter.cli.create_facility --name "Borehole ABC" --parent-code LR_MON_GM_CT --group BOREHOLE
    python -m adapter.cli.create_facility --name "Hand Pump XYZ" --parent-code LR_MON_GM_PV --group HAND_PUMP --coordinates "[-10.79, 6.31]"
"""

import argparse
import json
import os
import sys
from datetime import datetime
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
# Facility Creation
# =============================================================================


def get_parent_org_unit(parent_code: str) -> dict | None:
    """Fetch parent org unit by code."""
    response = dhis2_get(
        f"organisationUnits?filter=code:eq:{parent_code}&fields=id,name,code,level"
    )
    if response.status_code == 200:
        org_units = response.json().get("organisationUnits", [])
        if org_units:
            return org_units[0]
    return None


def get_org_unit_group(group_code: str) -> dict | None:
    """Fetch org unit group by code."""
    response = dhis2_get(
        f"organisationUnitGroups?filter=code:eq:{group_code}&fields=id,name,code"
    )
    if response.status_code == 200:
        groups = response.json().get("organisationUnitGroups", [])
        if groups:
            return groups[0]
    return None


def check_facility_exists(code: str) -> dict | None:
    """Check if facility with code already exists."""
    response = dhis2_get(
        f"organisationUnits?filter=code:eq:{code}&fields=id,name,code"
    )
    if response.status_code == 200:
        org_units = response.json().get("organisationUnits", [])
        if org_units:
            return org_units[0]
    return None


def generate_facility_code(name: str, parent_code: str) -> str:
    """Generate a unique facility code."""
    # Simple approach: parent_code + abbreviated name + timestamp
    import time

    # Take first letters of each word
    abbrev = "".join(word[0].upper() for word in name.split() if word)[:3]
    timestamp = str(int(time.time()))[-4:]
    return f"{parent_code}_{abbrev}_{timestamp}"


def create_facility(
    name: str,
    parent_code: str,
    group_code: str,
    code: str | None = None,
    short_name: str | None = None,
    coordinates: list | None = None,
    opening_date: str | None = None,
) -> dict | None:
    """Create a facility org unit."""
    print(f"\nCreating facility: {name}")

    # Validate parent
    parent = get_parent_org_unit(parent_code)
    if not parent:
        print(f"  ERROR: Parent org unit not found: {parent_code}")
        return None
    print(f"  Parent: {parent['name']} (Level {parent.get('level', '?')})")

    # Validate group
    group = get_org_unit_group(group_code)
    if not group:
        print(f"  ERROR: Org unit group not found: {group_code}")
        return None
    print(f"  Group: {group['name']}")

    # Generate or validate code
    if not code:
        code = generate_facility_code(name, parent_code)
    existing = check_facility_exists(code)
    if existing:
        print(f"  ERROR: Facility with code already exists: {code}")
        return None
    print(f"  Code: {code}")

    # Build org unit payload
    facility = {
        "name": name,
        "shortName": short_name or name[:50],
        "code": code,
        "parent": {"id": parent["id"]},
        "openingDate": opening_date or datetime.now().strftime("%Y-%m-%d"),
    }

    # Add geometry if coordinates provided
    if coordinates:
        facility["geometry"] = {
            "type": "Point",
            "coordinates": coordinates,
        }
        print(f"  Coordinates: {coordinates}")

    # Create org unit
    response = dhis2_post("metadata", {"organisationUnits": [facility]})

    if response.status_code not in [200, 201]:
        print(f"  ERROR: Failed to create org unit: {response.text[:200]}")
        return None

    result = response.json()
    if result.get("status") != "OK":
        print(f"  ERROR: {result}")
        return None

    # Fetch created org unit ID
    get_response = dhis2_get(f"organisationUnits?filter=code:eq:{code}&fields=id,name")
    if get_response.status_code != 200:
        print("  ERROR: Could not fetch created org unit")
        return None

    org_units = get_response.json().get("organisationUnits", [])
    if not org_units:
        print("  ERROR: Created org unit not found")
        return None

    facility_id = org_units[0]["id"]
    print(f"  Created: {facility_id}")

    # Add to org unit group
    add_to_group_response = dhis2_post(
        f"organisationUnitGroups/{group['id']}/organisationUnits/{facility_id}",
        {},
    )

    if add_to_group_response.status_code in [200, 201, 204]:
        print(f"  Added to group: {group['name']}")
    else:
        print(f"  WARNING: Failed to add to group: {add_to_group_response.status_code}")

    return {
        "id": facility_id,
        "name": name,
        "code": code,
        "group": group_code,
    }


# =============================================================================
# Main
# =============================================================================


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Create Facility Org Unit")
    parser.add_argument("--name", required=True, help="Facility name")
    parser.add_argument("--parent-code", required=True, help="Parent org unit code")
    parser.add_argument("--group", required=True, help="Org unit group code (e.g., BOREHOLE)")
    parser.add_argument("--code", help="Facility code (auto-generated if not provided)")
    parser.add_argument("--short-name", help="Short name (defaults to name)")
    parser.add_argument(
        "--coordinates",
        help='Coordinates as JSON array: "[longitude, latitude]"',
    )
    parser.add_argument(
        "--opening-date",
        help="Opening date (YYYY-MM-DD, defaults to today)",
    )
    args = parser.parse_args()

    # Parse coordinates if provided
    coordinates = None
    if args.coordinates:
        try:
            coordinates = json.loads(args.coordinates)
            if not isinstance(coordinates, list) or len(coordinates) != 2:
                print("ERROR: Coordinates must be [longitude, latitude]")
                sys.exit(1)
        except json.JSONDecodeError:
            print("ERROR: Invalid coordinates JSON")
            sys.exit(1)

    # Check connection
    print("=" * 60)
    print("Create Facility Org Unit")
    print("=" * 60)
    response = dhis2_get("system/info")
    if response.status_code != 200:
        print(f"ERROR: Cannot connect to DHIS2: {response.status_code}")
        sys.exit(1)

    # Create facility
    result = create_facility(
        name=args.name,
        parent_code=args.parent_code,
        group_code=args.group,
        code=args.code,
        short_name=args.short_name,
        coordinates=coordinates,
        opening_date=args.opening_date,
    )

    if result:
        print("\n" + "=" * 60)
        print("Success!")
        print("=" * 60)
        print(f"  ID: {result['id']}")
        print(f"  Name: {result['name']}")
        print(f"  Code: {result['code']}")
        print(f"  Group: {result['group']}")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
