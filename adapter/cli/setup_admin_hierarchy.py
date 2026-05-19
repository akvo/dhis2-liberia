#!/usr/bin/env python
"""
DHIS2 Admin Hierarchy Setup

Imports administrative organisation units from CSV file.
Creates the hierarchy: Country -> County -> District -> Community

Usage:
    python -m adapter.cli.setup_admin_hierarchy
    python -m adapter.cli.setup_admin_hierarchy --csv path/to/org_units.csv
    python -m adapter.cli.setup_admin_hierarchy --assign-user
"""

import argparse
import os
import sys
from pathlib import Path

import pandas as pd
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

# Default CSV path (project root)
DEFAULT_CSV = Path(__file__).parent.parent.parent / "org_units_sample.csv"

# Store created org units
created_org_units = {}


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
    print("DHIS2 Admin Hierarchy Setup")
    print("=" * 60)
    print(f"\nConnecting to {BASE_URL}...")

    response = dhis2_get("system/info")
    if response.status_code == 200:
        info = response.json()
        print(f"  DHIS2 Version: {info.get('version')}")
        return True
    else:
        print(f"  FAILED: {response.status_code}")
        return False


def import_org_units(csv_path: Path):
    """Import organisation units from CSV."""
    global created_org_units

    print(f"\n1. Importing Org Units from {csv_path.name}...")

    if not csv_path.exists():
        print(f"   ERROR: File not found: {csv_path}")
        return False

    # Read CSV
    df = pd.read_csv(csv_path)
    required_cols = ["name", "short_name", "code", "level", "parent_code"]
    missing_cols = [c for c in required_cols if c not in df.columns]
    if missing_cols:
        print(f"   ERROR: Missing columns: {missing_cols}")
        return False

    # Sort by level to ensure parents are created first
    df_sorted = df.sort_values("level")

    created_count = 0
    skipped_count = 0

    for _, row in df_sorted.iterrows():
        code = row["code"]
        name = row["name"]
        level = int(row["level"])
        indent = "  " * (level - 1)

        # Check if exists
        response = dhis2_get(
            f"organisationUnits?filter=code:eq:{code}&fields=id,name,code"
        )
        if response.status_code == 200:
            existing = response.json().get("organisationUnits", [])
            if existing:
                created_org_units[code] = existing[0]["id"]
                print(f"   {indent}Exists: {name}")
                skipped_count += 1
                continue

        # Determine parent
        parent_id = None
        parent_code = row.get("parent_code")
        if pd.notna(parent_code) and parent_code:
            parent_id = created_org_units.get(parent_code)
            if not parent_id:
                print(f"   {indent}ERROR: Parent not found: {parent_code}")
                continue

        # Create org unit
        org_unit = {
            "name": name,
            "shortName": row["short_name"],
            "code": code,
            "openingDate": "2020-01-01",
        }
        if parent_id:
            org_unit["parent"] = {"id": parent_id}

        response = dhis2_post("metadata", {"organisationUnits": [org_unit]})

        if response.status_code in [200, 201]:
            result = response.json()
            if result.get("status") == "OK":
                # Fetch created ID
                get_response = dhis2_get(
                    f"organisationUnits?filter=code:eq:{code}&fields=id"
                )
                if get_response.status_code == 200:
                    ou_data = get_response.json().get("organisationUnits", [])
                    if ou_data:
                        created_org_units[code] = ou_data[0]["id"]
                        print(f"   {indent}Created: {name}")
                        created_count += 1
                        continue

        print(f"   {indent}FAILED: {name}")

    print(f"\n   Summary: {created_count} created, {skipped_count} existing")
    print(f"   Total: {len(created_org_units)} org units")
    return True


def assign_user_to_org_units():
    """Assign current user to root org unit."""
    print("\n2. Assigning User to Org Units...")

    # Find root org unit (level 1)
    root_code = None
    for code in created_org_units:
        if code == "LR" or len(code) == 2:  # Assume 2-char code is root
            root_code = code
            break

    if not root_code:
        # Just use the first one
        root_code = next(iter(created_org_units), None)

    if not root_code:
        print("   SKIPPED: No org units found")
        return

    root_ou_id = created_org_units[root_code]

    # Get current user
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
        "teiSearchOrganisationUnits",
    ]
    for endpoint in endpoints:
        response = requests.post(
            f"{BASE_URL}/users/{user_id}/{endpoint}/{root_ou_id}",
            auth=AUTH,
            headers=HEADERS,
        )
        if response.status_code in [200, 201, 204]:
            success += 1

    print(f"   Assigned to {root_code} ({success}/3 endpoints)")


def print_summary():
    """Print setup summary."""
    print("\n" + "=" * 60)
    print("Setup Summary")
    print("=" * 60)
    print(f"  Org Units: {len(created_org_units)}")

    # Group by level (based on code length heuristic or count underscores)
    by_level = {}
    for code in created_org_units:
        level = code.count("_") + 1
        by_level.setdefault(level, []).append(code)

    for level in sorted(by_level.keys()):
        codes = by_level[level]
        print(f"    Level {level}: {len(codes)} org units")

    print("\nNext steps:")
    print("  1. Create facilities: python -m adapter.cli.create_facility")
    print("  2. Or import: python -m adapter.cli.import_facilities --csv facilities.csv")


# =============================================================================
# Main
# =============================================================================


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="DHIS2 Admin Hierarchy Setup")
    parser.add_argument(
        "--csv",
        type=Path,
        default=DEFAULT_CSV,
        help=f"Path to org units CSV (default: {DEFAULT_CSV})",
    )
    parser.add_argument(
        "--assign-user",
        action="store_true",
        help="Assign current user to root org unit",
    )
    args = parser.parse_args()

    if not check_connection():
        sys.exit(1)

    if not import_org_units(args.csv):
        sys.exit(1)

    if args.assign_user:
        assign_user_to_org_units()

    print_summary()


if __name__ == "__main__":
    main()
