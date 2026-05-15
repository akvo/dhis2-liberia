#!/usr/bin/env python
"""
DHIS2 Sunbird RC Sync Worker

A polling service that:
1. Watches DataStore for sync requests (sunbird-sync/queue)
2. Reads Sunbird credentials from DataStore (sunbird-sync/config)
3. Performs sync using the core sync engine
4. Writes results to DataStore (sunbird-sync/history)

Usage:
    python worker.py                    # Run with default 10s poll interval
    python worker.py --interval 5       # Poll every 5 seconds
    python worker.py --once             # Run once and exit (for cron)
"""

import argparse
import json
import logging
import os
import signal
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests

from sync import (
    DHIS2Config,
    SunbirdConfig,
    SyncConfig,
    SyncEngine,
    load_setup_config,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("worker")

# DataStore namespace and keys
NAMESPACE = "sunbird-sync"
CONFIG_KEY = "config"
QUEUE_KEY = "queue"
HISTORY_KEY = "history"


class Worker:
    """Polling worker for DHIS2 to Sunbird RC sync."""

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
        self.setup_config = load_setup_config()

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

    def datastore_create(self, key: str, data: dict) -> bool:
        """Create new key in DataStore."""
        url = f"{self.dhis2_url}/dataStore/{NAMESPACE}/{key}"
        response = requests.post(
            url,
            auth=self.dhis2_auth,
            headers={"Content-Type": "application/json"},
            json=data,
        )
        return response.status_code in [200, 201]

    def datastore_update(self, key: str, data: dict) -> bool:
        """Update existing key in DataStore."""
        url = f"{self.dhis2_url}/dataStore/{NAMESPACE}/{key}"
        response = requests.put(
            url,
            auth=self.dhis2_auth,
            headers={"Content-Type": "application/json"},
            json=data,
        )
        return response.status_code in [200, 204]

    def datastore_delete(self, key: str) -> bool:
        """Delete key from DataStore."""
        url = f"{self.dhis2_url}/dataStore/{NAMESPACE}/{key}"
        response = requests.delete(url, auth=self.dhis2_auth)
        return response.status_code in [200, 204]

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
        # Try update first, create if not exists
        if not self.datastore_update(QUEUE_KEY, empty_queue):
            return self.datastore_create(QUEUE_KEY, empty_queue)
        return True

    def get_pending_requests(self) -> list:
        """Get pending sync requests from queue."""
        queue = self.get_queue()
        if not queue:
            return []

        requests_list = queue.get("requests", [])
        # Filter to only pending requests
        return [r for r in requests_list if r.get("status") == "pending"]

    # -------------------------------------------------------------------------
    # Config Operations
    # -------------------------------------------------------------------------

    def get_sunbird_config(self) -> Optional[dict]:
        """Get Sunbird RC config from DataStore."""
        return self.datastore_get(CONFIG_KEY)

    def is_configured(self, config: dict) -> bool:
        """Check if Sunbird RC is properly configured."""
        required = ["sunbirdUrl", "keycloakUrl", "clientId", "clientSecret"]
        if not all(config.get(key) for key in required):
            return False
        # Check for at least one enabled program
        programs = config.get("programs", [])
        return any(p.get("enabled") and p.get("programId") and p.get("entityType") for p in programs)

    def get_program_config(self, config: dict, program_id: str) -> Optional[dict]:
        """Get program config by programId."""
        programs = config.get("programs", [])
        for prog in programs:
            if prog.get("programId") == program_id and prog.get("enabled"):
                return prog
        return None

    # -------------------------------------------------------------------------
    # History Operations
    # -------------------------------------------------------------------------

    def get_history(self) -> list:
        """Get sync history."""
        data = self.datastore_get(HISTORY_KEY)
        if data and isinstance(data, dict):
            return data.get("entries", [])
        return []

    def add_history_entry(self, entry: dict) -> bool:
        """Add entry to sync history."""
        history_data = self.datastore_get(HISTORY_KEY)

        if history_data is None:
            # Create new history
            history_data = {"entries": [entry]}
            return self.datastore_create(HISTORY_KEY, history_data)
        else:
            # Append to existing, keep last 100 entries
            entries = history_data.get("entries", [])
            entries.insert(0, entry)  # Most recent first
            entries = entries[:100]   # Keep last 100
            history_data["entries"] = entries
            return self.datastore_update(HISTORY_KEY, history_data)

    # -------------------------------------------------------------------------
    # Sync Operations
    # -------------------------------------------------------------------------

    def create_sync_engine(self, sunbird_config: dict, program_config: dict) -> SyncEngine:
        """Create a SyncEngine from DataStore config and program config."""
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
            entity_type=program_config.get("entityType", "WaterFacility"),
        )

        config = SyncConfig(
            dhis2=dhis2_config,
            sunbird=sunbird,
            program_id=program_config.get("programId"),
            setup_config=self.setup_config,
        )

        return SyncEngine(config)

    def process_sync_request(self, request: dict, sunbird_config: dict) -> dict:
        """Process a single sync request."""
        request_id = request.get("id", "unknown")
        program_id = request.get("programId")
        tei_ids = request.get("teiIds")  # Optional: specific TEIs to sync
        sync_type = request.get("type", "all")  # "all" or "selected"

        logger.info(f"Processing sync request {request_id} (program: {program_id}, type: {sync_type})")

        try:
            # Get program config
            program_config = self.get_program_config(sunbird_config, program_id)
            if not program_config:
                raise ValueError(f"Program {program_id} not found or not enabled")

            engine = self.create_sync_engine(sunbird_config, program_config)
            result = engine.run_sync(tei_ids=tei_ids)

            return {
                "requestId": request_id,
                "programId": program_id,
                "type": sync_type,
                "success": result.success,
                "total": result.total,
                "synced": result.synced,
                "failed": result.failed,
                "errors": result.errors,
                "startedAt": result.started_at,
                "finishedAt": result.finished_at,
            }

        except Exception as e:
            logger.error(f"Sync request {request_id} failed: {e}")
            return {
                "requestId": request_id,
                "programId": program_id,
                "type": sync_type,
                "success": False,
                "total": 0,
                "synced": 0,
                "failed": 0,
                "errors": [{"error": str(e)}],
                "startedAt": datetime.now().isoformat(),
                "finishedAt": datetime.now().isoformat(),
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
            result = self.process_sync_request(request, sunbird_config)

            # Add to history
            self.add_history_entry(result)
            processed += 1

            logger.info(
                f"Request {result['requestId']}: "
                f"synced={result['synced']}, failed={result['failed']}"
            )

        # Clear the queue after processing
        self.clear_queue()

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
        logger.info(f"Starting worker (poll interval: {self.poll_interval}s)")
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
        description="DHIS2 Sunbird RC Sync Worker"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=10,
        help="Poll interval in seconds (default: 10)"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run once and exit (for cron jobs)"
    )

    args = parser.parse_args()

    # Load environment
    load_env()

    dhis2_url = os.environ.get("DHIS2_URL", "http://localhost:9090")
    dhis2_username = os.environ.get("DHIS2_USERNAME", "admin")
    dhis2_password = os.environ.get("DHIS2_PASSWORD", "district")

    worker = Worker(
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
