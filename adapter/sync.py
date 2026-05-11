#!/usr/bin/env python
"""
DHIS2 to Sunbird RC Sync - Core Module

This module provides the core sync functionality that can be used by:
- CLI scripts (with .env credentials)
- Worker service (with DataStore credentials)
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration Classes
# =============================================================================


@dataclass
class DHIS2Config:
    """DHIS2 connection configuration."""
    base_url: str
    username: str
    password: str

    @property
    def auth(self) -> tuple:
        return (self.username, self.password)

    @property
    def api_url(self) -> str:
        url = self.base_url.rstrip("/")
        if not url.endswith("/api"):
            url = f"{url}/api"
        return url


@dataclass
class SunbirdConfig:
    """Sunbird RC connection configuration."""
    base_url: str
    keycloak_url: str
    client_id: str
    client_secret: str
    entity_type: str = "WaterFacility"


@dataclass
class SyncConfig:
    """Full sync configuration."""
    dhis2: DHIS2Config
    sunbird: SunbirdConfig
    program_id: Optional[str] = None  # Can be fetched dynamically
    setup_config: dict = field(default_factory=dict)


@dataclass
class SyncResult:
    """Result of a sync operation."""
    success: bool
    total: int = 0
    synced: int = 0
    failed: int = 0
    errors: list = field(default_factory=list)
    started_at: str = ""
    finished_at: str = ""

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "total": self.total,
            "synced": self.synced,
            "failed": self.failed,
            "errors": self.errors,
            "startedAt": self.started_at,
            "finishedAt": self.finished_at,
        }


# =============================================================================
# Sync Engine
# =============================================================================


class SyncEngine:
    """Core sync engine for DHIS2 to Sunbird RC synchronization."""

    def __init__(self, config: SyncConfig):
        self.config = config
        self.dhis2 = config.dhis2
        self.sunbird = config.sunbird
        self.setup_config = config.setup_config

        # Runtime state
        self.root_ou_id: Optional[str] = None
        self.program_id: Optional[str] = config.program_id
        self.attr_ids: dict = {}
        self.attr_codes: dict = {}
        self.org_unit_cache: dict = {}
        self.sunbird_token: Optional[str] = None

        # Build mappings from setup_config
        self._build_mappings()

    def _build_mappings(self):
        """Build attribute and option mappings from setup_config."""
        if not self.setup_config:
            return

        # Attribute codes list
        self.attr_codes_list = [
            attr["code"] for attr in self.setup_config.get("attributes", [])
        ]

        # Option mappings: attr_code -> {option_code: display_name}
        self.option_mappings = {}
        attr_to_option_set = {}
        for attr in self.setup_config.get("attributes", []):
            if "optionSetCode" in attr:
                attr_to_option_set[attr["optionSetCode"]] = attr["code"]

        for option_set in self.setup_config.get("option_sets", []):
            os_code = option_set["code"]
            attr_code = attr_to_option_set.get(os_code)
            if attr_code:
                self.option_mappings[attr_code] = {}
                for opt in option_set["options"]:
                    full_code = f"{os_code}_{opt['code']}"
                    self.option_mappings[attr_code][full_code] = opt["name"]

        # Other config
        self.sync_status = self.setup_config.get("sync_status", {
            "pending": "PENDING",
            "synced": "SYNCED",
            "failed": "FAILED",
        })

    # -------------------------------------------------------------------------
    # DHIS2 API Methods
    # -------------------------------------------------------------------------

    def dhis2_get(self, endpoint: str) -> requests.Response:
        """GET request to DHIS2 API."""
        url = f"{self.dhis2.api_url}/{endpoint}"
        return requests.get(
            url,
            auth=self.dhis2.auth,
            headers={"Accept": "application/json"},
        )

    def dhis2_put(self, endpoint: str, data: dict) -> requests.Response:
        """PUT request to DHIS2 API."""
        url = f"{self.dhis2.api_url}/{endpoint}"
        return requests.put(
            url,
            auth=self.dhis2.auth,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json=data,
        )

    def fetch_dhis2_metadata(self) -> bool:
        """Fetch DHIS2 IDs dynamically. Must be called before sync."""
        logger.info("Fetching DHIS2 metadata...")

        # Fetch root org unit (level 1)
        response = self.dhis2_get(
            "organisationUnits?filter=level:eq:1&fields=id,name&paging=false"
        )
        if response.status_code != 200:
            raise Exception(f"Failed to fetch root org unit: {response.status_code}")

        org_units = response.json().get("organisationUnits", [])
        if not org_units:
            raise Exception("No root organisation unit found")
        self.root_ou_id = org_units[0]["id"]
        logger.info(f"Root OU: {self.root_ou_id}")

        # Fetch program by code or use provided ID
        if not self.program_id:
            prog_code = self.setup_config.get("program", {}).get("code")
            if prog_code:
                response = self.dhis2_get(
                    f"programs?filter=code:eq:{prog_code}&fields=id,name&paging=false"
                )
                if response.status_code != 200:
                    raise Exception(f"Failed to fetch program: {response.status_code}")
                programs = response.json().get("programs", [])
                if not programs:
                    raise Exception(f"Program {prog_code} not found")
                self.program_id = programs[0]["id"]

        logger.info(f"Program: {self.program_id}")

        # Fetch tracked entity attributes by codes
        if self.attr_codes_list:
            codes_param = ",".join(self.attr_codes_list)
            response = self.dhis2_get(
                f"trackedEntityAttributes?filter=code:in:[{codes_param}]"
                f"&fields=id,code&paging=false"
            )
            if response.status_code != 200:
                raise Exception(f"Failed to fetch attributes: {response.status_code}")

            attributes = response.json().get("trackedEntityAttributes", [])
            self.attr_ids = {attr["code"]: attr["id"] for attr in attributes}
            self.attr_codes = {v: k for k, v in self.attr_ids.items()}
            logger.info(f"Loaded {len(self.attr_ids)} attributes")

        return True

    def resolve_org_unit(self, uid: str) -> Optional[str]:
        """Convert org unit UID to name."""
        if not uid:
            return None
        if uid in self.org_unit_cache:
            return self.org_unit_cache[uid]

        response = self.dhis2_get(f"organisationUnits/{uid}?fields=name")
        if response.status_code == 200:
            name = response.json().get("name")
            self.org_unit_cache[uid] = name
            return name
        return None

    def get_attribute_value(self, tei: dict, attr_code: str) -> Optional[str]:
        """Extract attribute value from TEI by attribute code."""
        attr_id = self.attr_ids.get(attr_code)
        if not attr_id:
            return None
        for attr in tei.get("attributes", []):
            if attr.get("attribute") == attr_id:
                return attr.get("value")
        return None

    def option_code_to_name(self, code: str, attr_code: str) -> Optional[str]:
        """Convert DHIS2 option code to display name."""
        if not code:
            return None
        option_map = self.option_mappings.get(attr_code, {})
        return option_map.get(code, code)

    # -------------------------------------------------------------------------
    # Sunbird RC API Methods
    # -------------------------------------------------------------------------

    def get_sunbird_token(self) -> str:
        """Get OAuth2 access token from Keycloak."""
        data = {
            "client_id": self.sunbird.client_id,
            "client_secret": self.sunbird.client_secret,
            "grant_type": "client_credentials",
        }
        response = requests.post(self.sunbird.keycloak_url, data=data)
        if response.status_code == 200:
            self.sunbird_token = response.json().get("access_token")
            return self.sunbird_token
        raise Exception(
            f"Failed to get Sunbird token: {response.status_code} {response.text}"
        )

    def sunbird_post(self, endpoint: str, data: dict) -> requests.Response:
        """POST request to Sunbird RC API."""
        url = f"{self.sunbird.base_url.rstrip('/')}/{endpoint}"
        return requests.post(
            url,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.sunbird_token}",
            },
            json=data,
        )

    def sunbird_get(self, endpoint: str) -> requests.Response:
        """GET request to Sunbird RC API."""
        url = f"{self.sunbird.base_url.rstrip('/')}/{endpoint}"
        return requests.get(
            url,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {self.sunbird_token}",
            },
        )

    # -------------------------------------------------------------------------
    # Sync Methods
    # -------------------------------------------------------------------------

    def fetch_pending_teis(self) -> list:
        """Fetch TEIs with syncStatus=PENDING from DHIS2."""
        sync_status_id = self.attr_ids.get("SYNC_STATUS_ATTR")
        if not sync_status_id:
            raise Exception("SYNC_STATUS_ATTR not found in attributes")

        pending_status = self.sync_status.get("pending", "PENDING")
        endpoint = (
            f"trackedEntityInstances"
            f"?ou={self.root_ou_id}"
            f"&ouMode=DESCENDANTS"
            f"&program={self.program_id}"
            f"&filter={sync_status_id}:eq:{pending_status}"
            f"&fields=*"
            f"&paging=false"
        )
        response = self.dhis2_get(endpoint)
        if response.status_code != 200:
            raise Exception(f"Failed to fetch TEIs: {response.status_code}")

        return response.json().get("trackedEntityInstances", [])

    def transform_tei_to_sunbird(self, tei: dict) -> dict:
        """Transform DHIS2 TEI to Sunbird RC format."""
        geo_code = self.get_attribute_value(tei, "GEO_CODE")

        # Resolve org unit UIDs to names
        county_uid = self.get_attribute_value(tei, "COUNTY")
        district_uid = self.get_attribute_value(tei, "DISTRICT")
        community_uid = self.get_attribute_value(tei, "COMMUNITY")

        county_name = self.resolve_org_unit(county_uid)
        district_name = self.resolve_org_unit(district_uid)
        community_name = self.resolve_org_unit(community_uid)

        # Get coordinates from TEI geometry
        geometry = tei.get("geometry")
        coordinates = None
        if geometry and geometry.get("type") == "Point":
            coords = geometry.get("coordinates", [])
            if len(coords) >= 2:
                coordinates = {"lat": coords[1], "lon": coords[0]}

        # Map option codes to display names
        water_point_type = self.option_code_to_name(
            self.get_attribute_value(tei, "WATER_POINT_TYPE_ATTR"),
            "WATER_POINT_TYPE_ATTR"
        )
        extraction_type = self.option_code_to_name(
            self.get_attribute_value(tei, "EXTRACTION_TYPE_ATTR"),
            "EXTRACTION_TYPE_ATTR"
        )
        pump_type = self.option_code_to_name(
            self.get_attribute_value(tei, "PUMP_TYPE_ATTR"),
            "PUMP_TYPE_ATTR"
        )
        installer = self.option_code_to_name(
            self.get_attribute_value(tei, "INSTALLER"),
            "INSTALLER"
        )
        owner = self.option_code_to_name(
            self.get_attribute_value(tei, "OWNER"),
            "OWNER"
        )

        # Build payload
        sunbird_data = {
            "geoCode": geo_code,
            "waterPointType": water_point_type,
            "location": {
                "county": county_name,
                "district": district_name,
                "community": community_name,
            },
        }

        if coordinates:
            sunbird_data["location"]["coordinates"] = coordinates

        # Optional fields
        if extraction_type:
            sunbird_data["extractionType"] = extraction_type
        if pump_type:
            sunbird_data["pumpType"] = pump_type
        if installer:
            sunbird_data["installer"] = installer
        if owner:
            sunbird_data["owner"] = owner

        num_taps = self.get_attribute_value(tei, "NUM_TAPS")
        if num_taps:
            sunbird_data["numTaps"] = int(num_taps)

        has_depth_info = self.get_attribute_value(tei, "HAS_DEPTH_INFO")
        if has_depth_info is not None:
            sunbird_data["hasDepthInfo"] = has_depth_info == "true"

        depth_metres = self.get_attribute_value(tei, "DEPTH_METRES")
        if depth_metres:
            sunbird_data["depthMetres"] = float(depth_metres)

        funder = self.get_attribute_value(tei, "FUNDER")
        if funder:
            sunbird_data["funder"] = funder

        photo_url = self.get_attribute_value(tei, "PHOTO_URL")
        if photo_url:
            sunbird_data["photoUrl"] = photo_url

        return sunbird_data

    def update_tei_status(
        self,
        tei_id: str,
        org_unit_id: str,
        status: str,
        osid: str = None,
        wf_id: str = None
    ) -> bool:
        """Update TEI sync status and IDs."""
        attributes = [
            {"attribute": self.attr_ids["SYNC_STATUS_ATTR"], "value": status},
        ]
        if osid:
            attributes.append({"attribute": self.attr_ids["SUNBIRD_OSID"], "value": osid})
        if wf_id:
            attributes.append({"attribute": self.attr_ids["WF_ID"], "value": wf_id})

        payload = {"orgUnit": org_unit_id, "attributes": attributes}
        response = self.dhis2_put(f"trackedEntityInstances/{tei_id}", payload)
        return response.status_code in [200, 204]

    def sync_single_tei(self, tei: dict) -> tuple[bool, Optional[str]]:
        """Sync a single TEI to Sunbird RC. Returns (success, error_message)."""
        tei_id = tei.get("trackedEntityInstance")
        org_unit_id = tei.get("orgUnit")
        geo_code = self.get_attribute_value(tei, "GEO_CODE")

        logger.info(f"Syncing TEI {tei_id} (geoCode: {geo_code})...")

        try:
            # Transform to Sunbird RC format
            sunbird_data = self.transform_tei_to_sunbird(tei)

            # POST to Sunbird RC
            entity_type = self.sunbird.entity_type
            response = self.sunbird_post(entity_type, sunbird_data)

            if response.status_code not in [200, 201]:
                error = f"Sunbird RC create failed: {response.status_code}"
                self.update_tei_status(
                    tei_id, org_unit_id, self.sync_status["failed"]
                )
                return False, error

            # Extract osid from response
            result = response.json()
            osid = result.get("result", {}).get(entity_type, {}).get("osid")

            if not osid:
                self.update_tei_status(
                    tei_id, org_unit_id, self.sync_status["failed"]
                )
                return False, "No osid in response"

            # GET the created record to fetch wfId
            get_response = self.sunbird_get(f"{entity_type}/{osid}")

            wf_id = ""
            if get_response.status_code == 200:
                facility = get_response.json()
                wf_id = facility.get("wfId", "")

            # Update DHIS2 with IDs
            if self.update_tei_status(
                tei_id, org_unit_id, self.sync_status["synced"], osid, wf_id
            ):
                logger.info(f"SUCCESS: osid={osid}, wfId={wf_id}")
                return True, None
            else:
                return False, "Could not update DHIS2"

        except Exception as e:
            logger.error(f"Error syncing TEI {tei_id}: {e}")
            self.update_tei_status(
                tei_id, org_unit_id, self.sync_status["failed"]
            )
            return False, str(e)

    def run_sync(self, tei_ids: list[str] = None) -> SyncResult:
        """
        Run sync operation.

        Args:
            tei_ids: Optional list of specific TEI IDs to sync.
                    If None, syncs all pending TEIs.

        Returns:
            SyncResult with sync statistics.
        """
        result = SyncResult(
            success=False,
            started_at=datetime.now().isoformat(),
        )

        try:
            # Fetch DHIS2 metadata
            self.fetch_dhis2_metadata()

            # Get Sunbird RC token
            logger.info("Authenticating with Sunbird RC...")
            self.get_sunbird_token()
            logger.info("Token acquired successfully")

            # Fetch TEIs to sync
            logger.info("Fetching TEIs to sync...")
            all_teis = self.fetch_pending_teis()

            # Filter to specific IDs if provided
            if tei_ids:
                teis = [
                    tei for tei in all_teis
                    if tei.get("trackedEntityInstance") in tei_ids
                ]
            else:
                teis = all_teis

            logger.info(f"Found {len(teis)} records to sync")
            result.total = len(teis)

            if not teis:
                result.success = True
                result.finished_at = datetime.now().isoformat()
                return result

            # Sync each TEI
            for tei in teis:
                success, error = self.sync_single_tei(tei)
                if success:
                    result.synced += 1
                else:
                    result.failed += 1
                    if error:
                        result.errors.append({
                            "teiId": tei.get("trackedEntityInstance"),
                            "error": error,
                        })

            result.success = result.failed == 0
            result.finished_at = datetime.now().isoformat()

        except Exception as e:
            logger.error(f"Sync failed: {e}")
            result.errors.append({"error": str(e)})
            result.finished_at = datetime.now().isoformat()

        return result


# =============================================================================
# Helper Functions
# =============================================================================


def load_setup_config(config_path: Path = None) -> dict:
    """Load setup configuration from JSON file."""
    if config_path is None:
        config_path = Path(__file__).parent / "setup_config.json"

    if not config_path.exists():
        raise Exception(f"Config file not found: {config_path}")

    with open(config_path) as f:
        return json.load(f)


def create_sync_engine_from_env(
    dhis2_url: str = None,
    dhis2_username: str = None,
    dhis2_password: str = None,
    sunbird_url: str = None,
    keycloak_url: str = None,
    client_id: str = None,
    client_secret: str = None,
    entity_type: str = "WaterFacility",
    program_id: str = None,
    setup_config: dict = None,
) -> SyncEngine:
    """Create a SyncEngine from environment/parameters."""
    import os

    dhis2_config = DHIS2Config(
        base_url=dhis2_url or os.environ.get("DHIS2_URL", "http://localhost:9090"),
        username=dhis2_username or os.environ.get("DHIS2_USERNAME", "admin"),
        password=dhis2_password or os.environ.get("DHIS2_PASSWORD", "district"),
    )

    sunbird_config = SunbirdConfig(
        base_url=sunbird_url or os.environ.get("SUNBIRD_URL", "http://localhost:8081/api/v1"),
        keycloak_url=keycloak_url or os.environ.get(
            "KEYCLOAK_URL",
            "http://keycloak:8080/auth/realms/sunbird-rc/protocol/openid-connect/token"
        ),
        client_id=client_id or os.environ.get("SUNBIRD_CLIENT_ID", "demo-api"),
        client_secret=client_secret or os.environ.get("SUNBIRD_CLIENT_SECRET", ""),
        entity_type=entity_type,
    )

    if setup_config is None:
        setup_config = load_setup_config()

    config = SyncConfig(
        dhis2=dhis2_config,
        sunbird=sunbird_config,
        program_id=program_id,
        setup_config=setup_config,
    )

    return SyncEngine(config)
