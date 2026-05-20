#!/usr/bin/env python
"""
Create Random Test Facilities

Generates random facility org units for testing pagination and sync.

Usage:
    python -m adapter.cli.create_random_facilities --count 50
    python -m adapter.cli.create_random_facilities --count 100 --group BOREHOLE
"""

import argparse
import os
import random
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

# Facility types (group codes)
FACILITY_TYPES = [
    "BOREHOLE",
    "HAND_PUMP",
    "PROTECTED_WELL",
    "UNPROTECTED_WELL",
    "PIPED_WATER",
    "SPRING",
    "RAINWATER",
    "SURFACE_WATER",
]

# Liberia approximate bounding box for coordinates
LIBERIA_BOUNDS = {
    "min_lon": -11.5,
    "max_lon": -7.4,
    "min_lat": 4.3,
    "max_lat": 8.6,
}

# Name prefixes for different facility types
NAME_PREFIXES = {
    "BOREHOLE": ["Community", "Village", "Town", "Central", "Main", "New"],
    "HAND_PUMP": ["Public", "School", "Market", "Clinic", "Church", "Mosque"],
    "PROTECTED_WELL": ["Protected", "Covered", "Safe", "Clean", "Community"],
    "UNPROTECTED_WELL": ["Open", "Traditional", "Old", "Village"],
    "PIPED_WATER": ["Municipal", "Public", "Town", "District"],
    "SPRING": ["Natural", "Mountain", "Forest", "Valley"],
    "RAINWATER": ["Rooftop", "Collection", "Storage"],
    "SURFACE_WATER": ["River", "Stream", "Pond", "Lake"],
}

# Name suffixes
NAME_SUFFIXES = [
    "Water Point",
    "Well",
    "Pump",
    "Source",
    "Supply",
    "Facility",
    "Station",
]


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


def get_communities() -> list[dict]:
    """Fetch all community-level org units (level 5 - facilities' parents)."""
    response = dhis2_get(
        "organisationUnits?filter=level:eq:5&fields=id,name,code&paging=false"
    )
    if response.status_code == 200:
        return response.json().get("organisationUnits", [])

    # Try level 4 if level 5 doesn't exist
    response = dhis2_get(
        "organisationUnits?filter=level:eq:4&fields=id,name,code&paging=false"
    )
    if response.status_code == 200:
        return response.json().get("organisationUnits", [])

    return []


def get_org_unit_groups() -> dict[str, str]:
    """Fetch all org unit groups and return code->id mapping."""
    response = dhis2_get(
        "organisationUnitGroups?fields=id,code&paging=false"
    )
    if response.status_code == 200:
        groups = response.json().get("organisationUnitGroups", [])
        return {g["code"]: g["id"] for g in groups if g.get("code")}
    return {}


def get_existing_codes() -> set[str]:
    """Get all existing facility codes to avoid duplicates."""
    response = dhis2_get(
        "organisationUnits?filter=level:ge:5&fields=code&paging=false"
    )
    if response.status_code == 200:
        org_units = response.json().get("organisationUnits", [])
        return {ou.get("code") for ou in org_units if ou.get("code")}
    return set()


# =============================================================================
# Random Generation
# =============================================================================


def generate_random_name(group_code: str, index: int) -> str:
    """Generate a random facility name."""
    prefixes = NAME_PREFIXES.get(group_code, ["Community"])
    prefix = random.choice(prefixes)
    suffix = random.choice(NAME_SUFFIXES)
    return f"{prefix} {suffix} {index}"


def generate_random_code(parent_code: str, group_code: str, existing_codes: set) -> str:
    """Generate a unique random facility code."""
    import time

    # Group abbreviation
    group_abbrev = group_code[:2].upper()

    # Generate until unique
    for _ in range(100):
        random_part = f"{random.randint(1000, 9999)}"
        code = f"{parent_code}_{group_abbrev}_{random_part}"
        if code not in existing_codes:
            existing_codes.add(code)
            return code

    # Fallback with timestamp
    timestamp = str(int(time.time()))[-6:]
    return f"{parent_code}_{group_abbrev}_{timestamp}"


def generate_random_coordinates(parent_coords: list = None) -> list:
    """Generate random coordinates within Liberia."""
    if parent_coords:
        # Generate near parent with small offset
        lon = parent_coords[0] + random.uniform(-0.05, 0.05)
        lat = parent_coords[1] + random.uniform(-0.05, 0.05)
    else:
        # Random within Liberia bounds
        lon = random.uniform(LIBERIA_BOUNDS["min_lon"], LIBERIA_BOUNDS["max_lon"])
        lat = random.uniform(LIBERIA_BOUNDS["min_lat"], LIBERIA_BOUNDS["max_lat"])

    # Round to 6 decimal places
    return [round(lon, 6), round(lat, 6)]


# =============================================================================
# Facility Creation
# =============================================================================


def create_facilities_batch(
    count: int,
    group_filter: str | None = None,
) -> tuple[int, int]:
    """Create multiple random facilities."""
    print("Fetching communities...")
    communities = get_communities()
    if not communities:
        print("ERROR: No communities found")
        return 0, 0
    print(f"  Found {len(communities)} communities")

    print("Fetching org unit groups...")
    groups = get_org_unit_groups()
    available_groups = [g for g in FACILITY_TYPES if g in groups]
    if group_filter:
        if group_filter not in groups:
            print(f"ERROR: Group {group_filter} not found")
            return 0, 0
        available_groups = [group_filter]
    print(f"  Available groups: {', '.join(available_groups)}")

    print("Fetching existing codes...")
    existing_codes = get_existing_codes()
    print(f"  Found {len(existing_codes)} existing facilities")

    print(f"\nCreating {count} random facilities...")
    print("-" * 60)

    success_count = 0
    error_count = 0

    # Prepare all facilities
    facilities = []
    facility_groups = []  # Track which group each facility belongs to

    for i in range(count):
        # Random community
        community = random.choice(communities)
        parent_code = community.get("code", "")
        parent_id = community["id"]

        # Random group
        group_code = random.choice(available_groups)
        group_id = groups[group_code]

        # Generate name and code
        name = generate_random_name(group_code, i + 1)
        code = generate_random_code(parent_code, group_code, existing_codes)
        short_name = name[:50]

        # Random coordinates
        coordinates = generate_random_coordinates()

        facility = {
            "name": name,
            "shortName": short_name,
            "code": code,
            "parent": {"id": parent_id},
            "openingDate": "2024-01-01",
            "geometry": {
                "type": "Point",
                "coordinates": coordinates,
            },
        }
        facilities.append(facility)
        facility_groups.append((code, group_id, group_code))

    # Create facilities in batch
    print(f"Creating {len(facilities)} org units...")
    response = dhis2_post("metadata", {"organisationUnits": facilities})

    if response.status_code not in [200, 201]:
        print(f"ERROR: Batch creation failed: {response.text[:500]}")
        return 0, count

    result = response.json()
    if result.get("status") != "OK":
        print(f"ERROR: {result}")
        return 0, count

    created_count = result.get("stats", {}).get("created", 0)
    print(f"  Created: {created_count} org units")

    # Fetch created org unit IDs
    print("Fetching created org unit IDs...")
    codes = [f[0] for f in facility_groups]
    code_to_id = {}

    # Fetch in batches of 50
    for i in range(0, len(codes), 50):
        batch_codes = codes[i:i+50]
        filter_param = ",".join(batch_codes)
        response = dhis2_get(
            f"organisationUnits?filter=code:in:[{filter_param}]&fields=id,code&paging=false"
        )
        if response.status_code == 200:
            for ou in response.json().get("organisationUnits", []):
                code_to_id[ou["code"]] = ou["id"]

    print(f"  Found {len(code_to_id)} org unit IDs")

    # Add to groups
    print("Adding to org unit groups...")
    for code, group_id, group_code in facility_groups:
        facility_id = code_to_id.get(code)
        if not facility_id:
            error_count += 1
            continue

        response = dhis2_post(
            f"organisationUnitGroups/{group_id}/organisationUnits/{facility_id}",
            {},
        )

        if response.status_code in [200, 201, 204]:
            success_count += 1
        else:
            error_count += 1

    return success_count, error_count


# =============================================================================
# Main
# =============================================================================


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Create Random Test Facilities")
    parser.add_argument(
        "--count",
        type=int,
        default=10,
        help="Number of facilities to create (default: 10)",
    )
    parser.add_argument(
        "--group",
        choices=FACILITY_TYPES,
        help="Specific facility type (random if not specified)",
    )
    args = parser.parse_args()

    # Check connection
    print("=" * 60)
    print("Create Random Test Facilities")
    print("=" * 60)
    response = dhis2_get("system/info")
    if response.status_code != 200:
        print(f"ERROR: Cannot connect to DHIS2: {response.status_code}")
        sys.exit(1)

    print(f"Connected to DHIS2")
    print(f"Creating {args.count} random facilities...")
    if args.group:
        print(f"Group filter: {args.group}")

    success, errors = create_facilities_batch(
        count=args.count,
        group_filter=args.group,
    )

    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"  Success: {success}")
    print(f"  Errors:  {errors}")
    print(f"  Total:   {success + errors}")

    if errors > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
