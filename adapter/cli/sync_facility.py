#!/usr/bin/env python
"""
CLI tool for manual DHIS2 to Sunbird RC sync.

Usage:
    python sync_facility.py              # Run sync
    python sync_facility.py --test-dhis2 # Test DHIS2 connection
    python sync_facility.py --test-sunbird # Test Sunbird RC connection
"""

import argparse
import logging
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sync import create_sync_engine_from_env, load_setup_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def load_env():
    """Load environment variables from .env file."""
    # Look for .env in project root (two levels up from cli/)
    env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())


def run_sync():
    """Run the sync operation."""
    print("=" * 60)
    print("DHIS2 -> Sunbird RC Sync (CLI)")
    print("=" * 60)

    try:
        setup_config = load_setup_config()
        engine = create_sync_engine_from_env(setup_config=setup_config)
        result = engine.run_sync()

        print("\n" + "=" * 60)
        print("Sync Summary")
        print("=" * 60)
        print(f"  Total processed: {result.total}")
        print(f"  Successful: {result.synced}")
        print(f"  Failed: {result.failed}")
        print(f"  Started: {result.started_at}")
        print(f"  Finished: {result.finished_at}")

        if result.errors:
            print("\nErrors:")
            for error in result.errors:
                print(f"  - {error}")

        return result.success

    except Exception as e:
        logger.error(f"Sync failed: {e}")
        return False


def test_dhis2():
    """Test DHIS2 connection."""
    print("Testing DHIS2 connection...")
    try:
        setup_config = load_setup_config()
        engine = create_sync_engine_from_env(setup_config=setup_config)

        response = engine.dhis2_get("system/info")
        if response.status_code == 200:
            info = response.json()
            print(f"  Connected to DHIS2 version {info.get('version')}")

            print("\nFetching DHIS2 metadata...")
            engine.fetch_dhis2_metadata()
            print(f"  Root OU: {engine.root_ou_id}")
            print(f"  Program: {engine.program_id}")
            print(f"  Attributes: {len(engine.attr_ids)} loaded")

            print("\nTesting pending TEI fetch...")
            teis = engine.fetch_pending_teis()
            print(f"  Found {len(teis)} pending TEIs")

            if teis:
                tei = teis[0]
                print("\n  Sample TEI:")
                print(f"    ID: {tei.get('trackedEntityInstance')}")
                print(f"    GeoCode: {engine.get_attribute_value(tei, 'GEO_CODE')}")
                county_uid = engine.get_attribute_value(tei, "COUNTY")
                county_name = engine.resolve_org_unit(county_uid)
                print(f"    County: {county_name}")

            return True
        else:
            print(f"  Failed: {response.status_code}")
            return False

    except Exception as e:
        print(f"  Failed: {e}")
        return False


def test_sunbird():
    """Test Sunbird RC connection."""
    print("Testing Sunbird RC connection...")
    try:
        setup_config = load_setup_config()
        engine = create_sync_engine_from_env(setup_config=setup_config)

        token = engine.get_sunbird_token()
        print("  Token acquired successfully")

        entity_type = engine.sunbird.entity_type
        response = engine.sunbird_get(entity_type)
        print(f"  {entity_type} API status: {response.status_code}")

        return True

    except Exception as e:
        print(f"  Failed: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="DHIS2 to Sunbird RC sync CLI tool"
    )
    parser.add_argument(
        "--test-dhis2",
        action="store_true",
        help="Test DHIS2 connection"
    )
    parser.add_argument(
        "--test-sunbird",
        action="store_true",
        help="Test Sunbird RC connection"
    )

    args = parser.parse_args()

    # Load environment variables
    load_env()

    if args.test_dhis2:
        sys.exit(0 if test_dhis2() else 1)
    elif args.test_sunbird:
        sys.exit(0 if test_sunbird() else 1)
    else:
        sys.exit(0 if run_sync() else 1)


if __name__ == "__main__":
    main()
