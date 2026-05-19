#!/usr/bin/env python
"""
DHIS2 Sunbird RC Sync Worker - Org Unit Based

A polling service that:
1. Watches DataStore for sync requests (sunbird-sync/queue)
2. Reads entity mappings from DataStore (sunbird-sync/entity-mappings)
3. Reads Sunbird credentials from DataStore (sunbird-sync/config)
4. Performs org unit sync using the org unit sync engine
5. Writes results to DataStore (sunbird-sync/history)
6. Updates stats in DataStore (sunbird-sync/stats)

Usage:
    python org_unit_worker.py                # Run with default 10s poll interval
    python org_unit_worker.py --interval 5   # Poll every 5 seconds
    python org_unit_worker.py --once         # Run once and exit (for cron)
"""

import argparse
import logging
import os
import signal
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests

from org_unit_sync import (
    DHIS2Config,
    SunbirdConfig,
    EntityMapping,
    OrgUnitSyncEngine,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("org_unit_worker")

# DataStore namespace and keys
NAMESPACE = "sunbird-sync"
CONFIG_KEY = "config"
ENTITY_MAPPINGS_KEY = "entity-mappings"
QUEUE_KEY = "queue"
HISTORY_KEY = "history"
STATS_KEY = "stats"
PROGRESS_KEY = "progress"


class OrgUnitWorker:
    """Polling worker for DHIS2 org unit to Sunbird RC sync."""

    def __init__(
        self,
        dhis2_url: str,
        dhis2_username: str,
        dhis2_password: str,
        poll_interval: int = 10,
    ):
        self.dhis2_url = dhis2_url.rstrip("/")
        if not self.dhis2_url.endswith("/api"):
            self.dhis2_url = f"{self.dhis2_url}/api"

        self.dhis2_auth = (dhis2_username, dhis2_password)
        self.poll_interval = poll_interval
        self.running = False

        # Cache for OSID attribute ID
        self._osid_attribute_id: Optional[str] = None

    # -------------------------------------------------------------------------
    # DHIS2 DataStore Operations
    # -------------------------------------------------------------------------

    def datastore_get(self, key: str) -> Optional[dict]:
        """Get value from DataStore."""
        url = f"{self.dhis2_url}/dataStore/{NAMESPACE}/{key}"
        response = requests.get(
            url,
            auth=self.dhis2_auth,
            headers={"Accept": "application/json"},
        )
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            return None
        else:
            logger.error(f"DataStore GET failed: {response.status_code}")
            return None

    def datastore_create(self, key: str, data) -> bool:
        """Create new key in DataStore."""
        url = f"{self.dhis2_url}/dataStore/{NAMESPACE}/{key}"
        response = requests.post(
            url,
            auth=self.dhis2_auth,
            headers={"Content-Type": "application/json"},
            json=data,
        )
        return response.status_code in [200, 201]

    def datastore_update(self, key: str, data) -> bool:
        """Update existing key in DataStore."""
        url = f"{self.dhis2_url}/dataStore/{NAMESPACE}/{key}"
        response = requests.put(
            url,
            auth=self.dhis2_auth,
            headers={"Content-Type": "application/json"},
            json=data,
        )
        return response.status_code in [200, 204]

    def datastore_upsert(self, key: str, data) -> bool:
        """Create or update key in DataStore."""
        if not self.datastore_update(key, data):
            return self.datastore_create(key, data)
        return True

    # -------------------------------------------------------------------------
    # DHIS2 Metadata Operations
    # -------------------------------------------------------------------------

    def get_osid_attribute_id(self) -> Optional[str]:
        """Get the ID of SUNBIRD_OSID attribute."""
        if self._osid_attribute_id:
            return self._osid_attribute_id

        url = f"{self.dhis2_url}/attributes?filter=code:eq:SUNBIRD_OSID&fields=id"
        response = requests.get(
            url,
            auth=self.dhis2_auth,
            headers={"Accept": "application/json"},
        )
        if response.status_code == 200:
            attrs = response.json().get("attributes", [])
            if attrs:
                self._osid_attribute_id = attrs[0]["id"]
                return self._osid_attribute_id
        return None

    # -------------------------------------------------------------------------
    # Config Operations
    # -------------------------------------------------------------------------

    def get_sunbird_config(self) -> Optional[dict]:
        """Get Sunbird RC config from DataStore."""
        return self.datastore_get(CONFIG_KEY)

    def get_entity_mappings(self) -> list:
        """Get entity mappings from DataStore."""
        data = self.datastore_get(ENTITY_MAPPINGS_KEY)
        if data and isinstance(data, list):
            return data
        return []

    def get_entity_mapping_by_id(self, mapping_id: str) -> Optional[dict]:
        """Get a specific entity mapping by ID."""
        mappings = self.get_entity_mappings()
        for mapping in mappings:
            if mapping.get("id") == mapping_id:
                return mapping
        return None

    def is_configured(self, config: dict) -> bool:
        """Check if Sunbird RC is properly configured."""
        required = ["sunbirdUrl", "keycloakUrl", "clientId", "clientSecret"]
        if not all(config.get(key) for key in required):
            return False

        # Check for OSID attribute
        if not self.get_osid_attribute_id():
            logger.warning("SUNBIRD_OSID attribute not found")
            return False

        # Check for at least one entity mapping
        mappings = self.get_entity_mappings()
        return len(mappings) > 0

    # -------------------------------------------------------------------------
    # Queue Operations
    # -------------------------------------------------------------------------

    def get_queue(self) -> Optional[dict]:
        """Get the current sync queue."""
        return self.datastore_get(QUEUE_KEY)

    def clear_queue(self) -> bool:
        """Clear the sync queue after processing."""
        empty_queue = {
            "requests": [],
            "lastCleared": datetime.now().isoformat(),
        }
        return self.datastore_upsert(QUEUE_KEY, empty_queue)

    def update_request_status(self, request_id: str, status: str) -> bool:
        """Update status of a specific request in queue."""
        queue = self.get_queue()
        if not queue:
            return False

        for request in queue.get("requests", []):
            if request.get("id") == request_id:
                request["status"] = status
                break

        return self.datastore_update(QUEUE_KEY, queue)

    def get_pending_requests(self) -> list:
        """Get pending sync requests from queue."""
        queue = self.get_queue()
        if not queue:
            return []

        requests_list = queue.get("requests", [])
        return [r for r in requests_list if r.get("status") == "pending"]

    # -------------------------------------------------------------------------
    # Progress Operations
    # -------------------------------------------------------------------------

    def update_progress(self, request_id: str, current: int, total: int, status: str) -> bool:
        """Update sync progress."""
        progress = {
            "requestId": request_id,
            "current": current,
            "total": total,
            "status": status,
            "updatedAt": datetime.now().isoformat(),
        }
        return self.datastore_upsert(PROGRESS_KEY, progress)

    def clear_progress(self) -> bool:
        """Clear progress after sync completes."""
        return self.datastore_upsert(PROGRESS_KEY, {"status": "idle"})

    # -------------------------------------------------------------------------
    # History Operations
    # -------------------------------------------------------------------------

    def get_history(self) -> list:
        """Get sync history."""
        data = self.datastore_get(HISTORY_KEY)
        if data and isinstance(data, list):
            return data
        return []

    def add_history_entry(self, entry: dict) -> bool:
        """Add entry to sync history."""
        history = self.get_history()

        # Add to beginning (most recent first)
        history.insert(0, entry)

        # Keep last 100 entries
        history = history[:100]

        return self.datastore_upsert(HISTORY_KEY, history)

    # -------------------------------------------------------------------------
    # Stats Operations
    # -------------------------------------------------------------------------

    def update_stats(self, entity_type: str, stats: dict) -> bool:
        """Update sync stats for an entity type."""
        all_stats = self.datastore_get(STATS_KEY) or {}
        all_stats[entity_type] = {
            **stats,
            "lastUpdated": datetime.now().isoformat(),
        }
        return self.datastore_upsert(STATS_KEY, all_stats)

    def calculate_stats(self, entity_mapping: dict) -> dict:
        """Calculate sync stats for an entity mapping."""
        group_ids = entity_mapping.get("orgUnitGroupIds", [])
        if not group_ids:
            return {"total": 0, "synced": 0, "pending": 0}

        osid_attr_id = self.get_osid_attribute_id()
        if not osid_attr_id:
            return {"total": 0, "synced": 0, "pending": 0}

        # Get total org units in groups
        group_filter = ",".join(group_ids)
        url = (
            f"{self.dhis2_url}/organisationUnits"
            f"?filter=organisationUnitGroups.id:in:[{group_filter}]"
            f"&fields=id,attributeValues[attribute[id],value]"
            f"&paging=false"
        )
        response = requests.get(
            url,
            auth=self.dhis2_auth,
            headers={"Accept": "application/json"},
        )

        if response.status_code != 200:
            return {"total": 0, "synced": 0, "pending": 0}

        org_units = response.json().get("organisationUnits", [])
        total = len(org_units)

        # Count synced (those with OSID)
        synced = 0
        for ou in org_units:
            for attr_value in ou.get("attributeValues", []):
                attr = attr_value.get("attribute", {})
                if attr.get("id") == osid_attr_id and attr_value.get("value"):
                    synced += 1
                    break

        return {
            "total": total,
            "synced": synced,
            "pending": total - synced,
        }

    # -------------------------------------------------------------------------
    # Sync Operations
    # -------------------------------------------------------------------------

    def create_sync_engine(
        self, sunbird_config: dict, entity_mapping: dict
    ) -> OrgUnitSyncEngine:
        """Create an OrgUnitSyncEngine from configs."""
        dhis2_config = DHIS2Config(
            base_url=self.dhis2_url.replace("/api", ""),
            username=self.dhis2_auth[0],
            password=self.dhis2_auth[1],
        )

        sunbird = SunbirdConfig(
            base_url=sunbird_config.get("sunbirdUrl", ""),
            keycloak_url=sunbird_config.get("keycloakUrl", ""),
            client_id=sunbird_config.get("clientId", ""),
            client_secret=sunbird_config.get("clientSecret", ""),
        )

        mapping = EntityMapping(
            id=entity_mapping.get("id", ""),
            entity_type=entity_mapping.get("entityType", "WaterFacility"),
            org_unit_group_ids=entity_mapping.get("orgUnitGroupIds", []),
            field_mappings=entity_mapping.get("fieldMappings", []),
        )

        osid_attr_id = self.get_osid_attribute_id()
        if not osid_attr_id:
            raise ValueError("SUNBIRD_OSID attribute not found")

        return OrgUnitSyncEngine(
            dhis2_config=dhis2_config,
            sunbird_config=sunbird,
            entity_mapping=mapping,
            osid_attribute_id=osid_attr_id,
        )

    def process_sync_request(self, request: dict, sunbird_config: dict) -> dict:
        """Process a single sync request."""
        request_id = request.get("id", str(uuid.uuid4()))
        entity_mapping_id = request.get("entityMappingId")
        org_unit_ids = request.get("orgUnitIds")  # Optional: specific org units
        sync_type = request.get("type", "all")  # "all" or "selected"

        logger.info(
            f"Processing sync request {request_id} "
            f"(entityMapping: {entity_mapping_id}, type: {sync_type})"
        )

        # Mark request as processing
        self.update_request_status(request_id, "processing")

        try:
            # Get entity mapping
            entity_mapping = self.get_entity_mapping_by_id(entity_mapping_id)
            if not entity_mapping:
                raise ValueError(f"Entity mapping {entity_mapping_id} not found")

            entity_type = entity_mapping.get("entityType", "Unknown")

            # Create sync engine
            engine = self.create_sync_engine(sunbird_config, entity_mapping)

            # Run sync
            result = engine.run_sync(org_unit_ids=org_unit_ids)

            # Update stats
            stats = self.calculate_stats(entity_mapping)
            stats["lastSync"] = datetime.now().isoformat()
            self.update_stats(entity_type, stats)

            # Build history entry
            history_entry = {
                "id": str(uuid.uuid4()),
                "timestamp": datetime.now().isoformat(),
                "entityMappingId": entity_mapping_id,
                "entityType": entity_type,
                "totalCount": result.total,
                "successCount": result.synced,
                "errorCount": result.failed,
                "results": result.results,
            }

            return history_entry

        except Exception as e:
            logger.error(f"Sync request {request_id} failed: {e}")
            return {
                "id": str(uuid.uuid4()),
                "timestamp": datetime.now().isoformat(),
                "entityMappingId": entity_mapping_id,
                "entityType": "Unknown",
                "totalCount": 0,
                "successCount": 0,
                "errorCount": 1,
                "results": [{"error": str(e)}],
            }

    def process_queue(self) -> int:
        """Process all pending requests in the queue. Returns count processed."""
        # Get Sunbird config
        sunbird_config = self.get_sunbird_config()
        if not sunbird_config:
            logger.debug("No Sunbird config found in DataStore")
            return 0

        if not self.is_configured(sunbird_config):
            logger.warning("Sunbird RC not fully configured")
            return 0

        # Get pending requests
        pending = self.get_pending_requests()
        if not pending:
            return 0

        logger.info(f"Found {len(pending)} pending sync request(s)")

        processed = 0
        for request in pending:
            # Update progress
            self.update_progress(
                request.get("id", ""),
                processed + 1,
                len(pending),
                "running",
            )

            # Process request
            result = self.process_sync_request(request, sunbird_config)

            # Add to history
            self.add_history_entry(result)
            processed += 1

            logger.info(
                f"Request completed: "
                f"synced={result['successCount']}, failed={result['errorCount']}"
            )

        # Clear queue and progress
        self.clear_queue()
        self.clear_progress()

        return processed

    # -------------------------------------------------------------------------
    # Main Loop
    # -------------------------------------------------------------------------

    def run_once(self) -> int:
        """Run a single poll cycle. Returns count of requests processed."""
        try:
            return self.process_queue()
        except Exception as e:
            logger.error(f"Error processing queue: {e}")
            return 0

    def run(self):
        """Run the polling loop."""
        logger.info(f"Starting org unit worker (poll interval: {self.poll_interval}s)")
        self.running = True

        # Handle graceful shutdown
        def signal_handler(signum, frame):
            logger.info("Received shutdown signal")
            self.running = False

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        while self.running:
            try:
                processed = self.process_queue()
                if processed > 0:
                    logger.info(f"Processed {processed} request(s)")
            except Exception as e:
                logger.error(f"Error in poll cycle: {e}")

            # Sleep in small increments to allow graceful shutdown
            for _ in range(self.poll_interval):
                if not self.running:
                    break
                time.sleep(1)

        logger.info("Worker stopped")


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


def main():
    parser = argparse.ArgumentParser(
        description="DHIS2 Sunbird RC Org Unit Sync Worker"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=10,
        help="Poll interval in seconds (default: 10)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run once and exit (for cron jobs)",
    )

    args = parser.parse_args()

    # Load environment
    load_env()

    dhis2_url = os.environ.get("DHIS2_URL", "http://localhost:9090")
    dhis2_username = os.environ.get("DHIS2_USERNAME", "admin")
    dhis2_password = os.environ.get("DHIS2_PASSWORD", "district")

    worker = OrgUnitWorker(
        dhis2_url=dhis2_url,
        dhis2_username=dhis2_username,
        dhis2_password=dhis2_password,
        poll_interval=args.interval,
    )

    if args.once:
        # Single run mode (for cron)
        processed = worker.run_once()
        logger.info(f"Single run complete: {processed} request(s) processed")
        sys.exit(0)
    else:
        # Continuous polling mode
        worker.run()


if __name__ == "__main__":
    main()
