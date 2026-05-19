#!/usr/bin/env python
"""
Bulk Import Facilities

Imports multiple facilities from a CSV file.

CSV Format:
    name,short_name,code,parent_code,group,longitude,latitude,opening_date
    Borehole ABC,BH ABC,BH_001,LR_MON_GM_CT,BOREHOLE,-10.79,6.31,2024-01-15
    Hand Pump XYZ,HP XYZ,HP_001,LR_MON_GM_PV,HAND_PUMP,-10.80,6.32,2024-01-20

Usage:
    python -m adapter.cli.import_facilities --csv facilities.csv
    python -m adapter.cli.import_facilities --csv facilities.csv --dry-run
"""

import argparse
import os
import sys
from datetime import datetime
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
# Data Fetching
# =============================================================================


def fetch_org_units() -> dict:
    """Fetch all org units as code -> id mapping."""
    response = dhis2_get("organisationUnits?fields=id,code&paging=false")
    if response.status_code == 200:
        return {
            ou["code"]: ou["id"]
            for ou in response.json().get("organisationUnits", [])
            if ou.get("code")
        }
    return {}


def fetch_org_unit_groups() -> dict:
    """Fetch all org unit groups as code -> id mapping."""
    response = dhis2_get("organisationUnitGroups?fields=id,code&paging=false")
    if response.status_code == 200:
        return {
            g["code"]: g["id"]
            for g in response.json().get("organisationUnitGroups", [])
            if g.get("code")
        }
    return {}


# =============================================================================
# Import Functions
# =============================================================================


def validate_csv(df: pd.DataFrame, org_units: dict, groups: dict) -> list:
    """Validate CSV data and return list of errors."""
    errors = []
    required_cols = ["name", "parent_code", "group"]

    # Check required columns
    missing_cols = [c for c in required_cols if c not in df.columns]
    if missing_cols:
        errors.append(f"Missing required columns: {missing_cols}")
        return errors

    # Validate each row
    for idx, row in df.iterrows():
        row_num = idx + 2  # Account for header and 0-indexing

        # Check parent exists
        parent_code = row.get("parent_code")
        if pd.isna(parent_code) or not parent_code:
            errors.append(f"Row {row_num}: Missing parent_code")
        elif parent_code not in org_units:
            errors.append(f"Row {row_num}: Parent not found: {parent_code}")

        # Check group exists
        group = row.get("group")
        if pd.isna(group) or not group:
            errors.append(f"Row {row_num}: Missing group")
        elif group not in groups:
            errors.append(f"Row {row_num}: Group not found: {group}")

        # Check name
        name = row.get("name")
        if pd.isna(name) or not name:
            errors.append(f"Row {row_num}: Missing name")

        # Check code uniqueness
        code = row.get("code")
        if pd.notna(code) and code in org_units:
            errors.append(f"Row {row_num}: Code already exists: {code}")

    return errors


def import_facilities(
    csv_path: Path, org_units: dict, groups: dict, dry_run: bool = False
) -> dict:
    """Import facilities from CSV."""
    print(f"\nImporting from {csv_path.name}...")

    # Read CSV
    df = pd.read_csv(csv_path)
    total = len(df)
    print(f"  Found {total} facilities")

    # Validate
    errors = validate_csv(df, org_units, groups)
    if errors:
        print(f"\n  Validation errors ({len(errors)}):")
        for error in errors[:10]:  # Show first 10
            print(f"    - {error}")
        if len(errors) > 10:
            print(f"    ... and {len(errors) - 10} more")
        return {"success": 0, "failed": total, "errors": errors}

    if dry_run:
        print("\n  DRY RUN - No changes made")
        print(f"  Would import {total} facilities")
        return {"success": total, "failed": 0, "dry_run": True}

    # Import facilities
    success = 0
    failed = 0
    failed_rows = []

    for idx, row in df.iterrows():
        name = row["name"]
        parent_code = row["parent_code"]
        group_code = row["group"]

        # Generate code if not provided
        code = row.get("code")
        if pd.isna(code) or not code:
            import time
            abbrev = "".join(word[0].upper() for word in str(name).split() if word)[:3]
            timestamp = str(int(time.time() * 1000))[-6:]
            code = f"{parent_code}_{abbrev}_{timestamp}"

        # Short name
        short_name = row.get("short_name")
        if pd.isna(short_name) or not short_name:
            short_name = str(name)[:50]

        # Opening date
        opening_date = row.get("opening_date")
        if pd.isna(opening_date) or not opening_date:
            opening_date = datetime.now().strftime("%Y-%m-%d")

        # Build org unit payload
        facility = {
            "name": str(name),
            "shortName": str(short_name),
            "code": str(code),
            "parent": {"id": org_units[parent_code]},
            "openingDate": str(opening_date),
        }

        # Add geometry if coordinates provided
        lon = row.get("longitude")
        lat = row.get("latitude")
        if pd.notna(lon) and pd.notna(lat):
            facility["geometry"] = {
                "type": "Point",
                "coordinates": [float(lon), float(lat)],
            }

        # Create org unit
        response = dhis2_post("metadata", {"organisationUnits": [facility]})

        if response.status_code not in [200, 201]:
            print(f"    FAILED: {name} - {response.status_code}")
            failed += 1
            failed_rows.append({"name": name, "error": response.text[:100]})
            continue

        result = response.json()
        if result.get("status") != "OK":
            print(f"    FAILED: {name} - {result}")
            failed += 1
            failed_rows.append({"name": name, "error": str(result)[:100]})
            continue

        # Fetch created ID
        get_response = dhis2_get(f"organisationUnits?filter=code:eq:{code}&fields=id")
        if get_response.status_code != 200:
            print(f"    FAILED: {name} - Could not fetch ID")
            failed += 1
            continue

        ou_data = get_response.json().get("organisationUnits", [])
        if not ou_data:
            print(f"    FAILED: {name} - Created but not found")
            failed += 1
            continue

        facility_id = ou_data[0]["id"]

        # Add to group
        add_response = dhis2_post(
            f"organisationUnitGroups/{groups[group_code]}/organisationUnits/{facility_id}",
            {},
        )

        if add_response.status_code in [200, 201, 204]:
            print(f"    Created: {name} -> {group_code}")
            success += 1
            # Update local cache
            org_units[code] = facility_id
        else:
            print(f"    PARTIAL: {name} - Created but not added to group")
            success += 1

    return {
        "success": success,
        "failed": failed,
        "failed_rows": failed_rows,
    }


# =============================================================================
# Main
# =============================================================================


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Bulk Import Facilities")
    parser.add_argument("--csv", type=Path, required=True, help="Path to facilities CSV")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate only, don't create facilities",
    )
    args = parser.parse_args()

    if not args.csv.exists():
        print(f"ERROR: File not found: {args.csv}")
        sys.exit(1)

    print("=" * 60)
    print("Bulk Import Facilities")
    print("=" * 60)

    # Check connection
    response = dhis2_get("system/info")
    if response.status_code != 200:
        print(f"ERROR: Cannot connect to DHIS2: {response.status_code}")
        sys.exit(1)
    print(f"Connected to {BASE_URL}")

    # Fetch existing data
    print("\nFetching existing data...")
    org_units = fetch_org_units()
    print(f"  Org units: {len(org_units)}")
    groups = fetch_org_unit_groups()
    print(f"  Groups: {len(groups)}")

    if not groups:
        print("\nERROR: No org unit groups found. Run setup_metadata.py first.")
        sys.exit(1)

    # Import
    result = import_facilities(args.csv, org_units, groups, args.dry_run)

    # Summary
    print("\n" + "=" * 60)
    print("Import Summary")
    print("=" * 60)
    print(f"  Success: {result['success']}")
    print(f"  Failed: {result['failed']}")

    if result.get("dry_run"):
        print("\n  This was a dry run. No changes were made.")
        print("  Run without --dry-run to import facilities.")

    if result["failed"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
