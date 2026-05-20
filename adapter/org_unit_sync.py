#!/usr/bin/env python
"""
DHIS2 to Sunbird RC Sync - Org Unit Based

This module provides sync functionality for org unit-based facility registration.
Org units are synced to Sunbird RC based on entity mappings configured in DataStore.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
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


@dataclass
class EntityMapping:
    """Mapping from org unit groups to Sunbird entity type."""
    id: str
    entity_type: str
    org_unit_group_ids: list[str]
    field_mappings: list[dict]  # [{source, target, required}]


@dataclass
class SyncResult:
    """Result of a sync operation."""
    success: bool
    total: int = 0
    synced: int = 0
    failed: int = 0
    results: list = field(default_factory=list)  # [{orgUnitId, orgUnitName, status, osid?, error?}]
    started_at: str = ""
    finished_at: str = ""

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "total": self.total,
            "synced": self.synced,
            "failed": self.failed,
            "results": self.results,
            "startedAt": self.started_at,
            "finishedAt": self.finished_at,
        }


# =============================================================================
# Org Unit Sync Engine
# =============================================================================


class OrgUnitSyncEngine:
    """Sync engine for org unit-based facility synchronization."""

    def __init__(
        self,
        dhis2_config: DHIS2Config,
        sunbird_config: SunbirdConfig,
        entity_mapping: EntityMapping,
        osid_attribute_id: str,
    ):
        self.dhis2 = dhis2_config
        self.sunbird = sunbird_config
        self.entity_mapping = entity_mapping
        self.osid_attribute_id = osid_attribute_id

        # Runtime state
        self.sunbird_token: Optional[str] = None
        self.org_unit_cache: dict = {}  # id -> org unit data

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

    def dhis2_patch(self, endpoint: str, data: dict) -> requests.Response:
        """PATCH request to DHIS2 API."""
        url = f"{self.dhis2.api_url}/{endpoint}"
        return requests.patch(
            url,
            auth=self.dhis2.auth,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json=data,
        )

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

    # -------------------------------------------------------------------------
    # Org Unit Methods
    # -------------------------------------------------------------------------

    def fetch_pending_org_units(self) -> list[dict]:
        """Fetch org units that need to be synced (no OSID)."""
        # Build filter for org unit groups
        group_ids = self.entity_mapping.org_unit_group_ids
        if not group_ids:
            logger.warning("No org unit groups configured")
            return []

        # Query org units in the mapped groups without OSID
        # Note: DHIS2 doesn't support filtering by null attribute directly,
        # so we fetch all and filter in Python
        group_filter = ",".join(group_ids)
        endpoint = (
            f"organisationUnits"
            f"?filter=organisationUnitGroups.id:in:[{group_filter}]"
            f"&fields=id,name,code,shortName,geometry,openingDate,"
            f"attributeValues[attribute[id,code],value],"
            f"ancestors[id,name,level],"
            f"organisationUnitGroups[id,code,displayName]"
            f"&paging=false"
        )

        response = self.dhis2_get(endpoint)
        if response.status_code != 200:
            raise Exception(f"Failed to fetch org units: {response.status_code}")

        all_org_units = response.json().get("organisationUnits", [])

        # Filter out those that already have OSID
        pending = []
        for ou in all_org_units:
            osid = self._get_osid_from_org_unit(ou)
            if not osid:
                pending.append(ou)

        return pending

    def fetch_org_units_by_ids(self, org_unit_ids: list[str]) -> list[dict]:
        """Fetch specific org units by ID."""
        if not org_unit_ids:
            return []

        ids_param = ",".join(org_unit_ids)
        endpoint = (
            f"organisationUnits"
            f"?filter=id:in:[{ids_param}]"
            f"&fields=id,name,code,shortName,geometry,openingDate,"
            f"attributeValues[attribute[id,code],value],"
            f"ancestors[id,name,level],"
            f"organisationUnitGroups[id,code,displayName]"
            f"&paging=false"
        )

        response = self.dhis2_get(endpoint)
        if response.status_code != 200:
            raise Exception(f"Failed to fetch org units: {response.status_code}")

        return response.json().get("organisationUnits", [])

    def _get_osid_from_org_unit(self, org_unit: dict) -> Optional[str]:
        """Extract SUNBIRD_OSID from org unit attribute values."""
        for attr_value in org_unit.get("attributeValues", []):
            attr = attr_value.get("attribute", {})
            if attr.get("id") == self.osid_attribute_id or attr.get("code") == "SUNBIRD_OSID":
                return attr_value.get("value")
        return None

    def _get_ancestor_by_level(self, org_unit: dict, level: int) -> Optional[str]:
        """Get ancestor name at a specific level."""
        for ancestor in org_unit.get("ancestors", []):
            if ancestor.get("level") == level:
                return ancestor.get("name")
        return None

    # -------------------------------------------------------------------------
    # Transformation
    # -------------------------------------------------------------------------

    def transform_org_unit(self, org_unit: dict) -> dict:
        """Transform DHIS2 org unit to Sunbird RC format using field mappings."""
        result = {}

        for mapping in self.entity_mapping.field_mappings:
            source = mapping.get("source")
            target = mapping.get("target")

            if not source or not target:
                continue

            value = self._extract_source_value(org_unit, source, mapping)

            if value is not None:
                self._set_nested_value(result, target, value)

        return result

    def _extract_source_value(self, org_unit: dict, source: str, mapping: dict = None):
        """Extract value from org unit based on source field specification."""
        # Handle constant values
        if source == "$constant":
            return mapping.get("constantValue") if mapping else None

        # Handle parent level syntax: parent[level=2].name
        if source.startswith("parent[level="):
            try:
                level_str = source.split("=")[1].split("]")[0]
                level = int(level_str)
                return self._get_ancestor_by_level(org_unit, level)
            except (IndexError, ValueError):
                return None

        # Handle parent.name (immediate parent)
        if source == "parent.name":
            ancestors = org_unit.get("ancestors", [])
            if ancestors:
                # Get the last ancestor (immediate parent)
                return ancestors[-1].get("name")
            return None

        # Handle geometry.coordinates[0] (longitude) and geometry.coordinates[1] (latitude)
        if source.startswith("geometry.coordinates["):
            geometry = org_unit.get("geometry")
            if geometry and geometry.get("type") == "Point":
                coords = geometry.get("coordinates", [])
                try:
                    index = int(source.split("[")[1].split("]")[0])
                    if len(coords) > index:
                        return coords[index]
                except (IndexError, ValueError):
                    pass
            return None

        # Handle geometry.coordinates (full coordinates)
        if source == "geometry.coordinates":
            geometry = org_unit.get("geometry")
            if geometry and geometry.get("type") == "Point":
                coords = geometry.get("coordinates", [])
                if len(coords) >= 2:
                    return {"lon": coords[0], "lat": coords[1]}
            return None

        # Handle attribute values: attribute.{CODE}
        if source.startswith("attribute."):
            attr_code = source.split(".", 1)[1]
            for attr_value in org_unit.get("attributeValues", []):
                attr = attr_value.get("attribute", {})
                if attr.get("code") == attr_code:
                    return attr_value.get("value")
            return None

        # Handle organisationUnitGroup.code and organisationUnitGroup.name
        if source == "organisationUnitGroup.code":
            groups = org_unit.get("organisationUnitGroups", [])
            if groups:
                return groups[0].get("code")
            return None

        if source == "organisationUnitGroup.name":
            groups = org_unit.get("organisationUnitGroups", [])
            if groups:
                return groups[0].get("displayName")
            return None

        # Handle direct fields
        return org_unit.get(source)

    def _set_nested_value(self, obj: dict, path: str, value):
        """Set a nested value in a dict using dot notation.

        Supports array syntax like 'externalApis[].platform' which creates:
        { "externalApis": [{ "platform": value }] }
        """
        parts = path.split(".")
        current = obj

        for i, part in enumerate(parts[:-1]):
            # Handle array syntax: fieldName[]
            if part.endswith("[]"):
                array_name = part[:-2]
                if array_name not in current:
                    current[array_name] = [{}]
                elif not current[array_name]:
                    current[array_name] = [{}]
                # Navigate into the first (and only) array element
                current = current[array_name][0]
            else:
                if part not in current:
                    current[part] = {}
                current = current[part]

        # Handle final part (also might have array syntax)
        final_part = parts[-1]
        if final_part.endswith("[]"):
            array_name = final_part[:-2]
            if array_name not in current:
                current[array_name] = []
            current[array_name].append(value)
        else:
            current[final_part] = value

    # -------------------------------------------------------------------------
    # OSID Update
    # -------------------------------------------------------------------------

    def update_org_unit_osid(self, org_unit_id: str, osid: str) -> bool:
        """Update org unit with SUNBIRD_OSID attribute value."""
        # First, get full org unit data (DHIS2 PATCH doesn't support nested objects)
        response = self.dhis2_get(f"organisationUnits/{org_unit_id}")
        if response.status_code != 200:
            logger.error(f"Failed to fetch org unit {org_unit_id}")
            return False

        org_unit = response.json()

        # Update or add OSID attribute
        attr_values = org_unit.get("attributeValues", [])
        osid_found = False

        for attr_value in attr_values:
            attr = attr_value.get("attribute", {})
            if attr.get("id") == self.osid_attribute_id:
                attr_value["value"] = osid
                osid_found = True
                break

        if not osid_found:
            attr_values.append({
                "attribute": {"id": self.osid_attribute_id},
                "value": osid,
            })

        org_unit["attributeValues"] = attr_values

        # Use PUT with full org unit (PATCH doesn't support nested attribute objects)
        response = self.dhis2_put(
            f"organisationUnits/{org_unit_id}",
            org_unit,
        )

        if response.status_code in [200, 204]:
            return True
        else:
            logger.error(f"Failed to update OSID: {response.status_code} {response.text}")
            return False

    # -------------------------------------------------------------------------
    # Sync Methods
    # -------------------------------------------------------------------------

    def sync_single_org_unit(self, org_unit: dict) -> dict:
        """
        Sync a single org unit to Sunbird RC.

        Returns:
            Dict with keys: orgUnitId, orgUnitName, status, osid?, error?
        """
        org_unit_id = org_unit.get("id")
        org_unit_name = org_unit.get("name")

        result = {
            "orgUnitId": org_unit_id,
            "orgUnitName": org_unit_name,
            "status": "error",
        }

        try:
            # Transform to Sunbird RC format
            sunbird_data = self.transform_org_unit(org_unit)

            # POST to Sunbird RC
            entity_type = self.entity_mapping.entity_type
            response = self.sunbird_post(entity_type, sunbird_data)

            if response.status_code not in [200, 201]:
                # Extract detailed error message from Sunbird response
                try:
                    error_data = response.json()
                    error_msg = error_data.get("params", {}).get("errmsg", "")
                    # Simplify the error message if it contains exception class names
                    if "UniqueIdentifierException" in error_msg:
                        # Extract the actual message after the last colon
                        parts = error_msg.split(":")
                        error_msg = parts[-1].strip() if parts else error_msg
                except Exception:
                    error_msg = response.text[:200]

                result["error"] = error_msg or f"Sunbird RC error: {response.status_code}"
                logger.error(f"Failed to sync {org_unit_name}: {error_msg}")
                return result

            # Extract OSID from response
            response_data = response.json()
            osid = response_data.get("result", {}).get(entity_type, {}).get("osid")

            if not osid:
                result["error"] = "No OSID in response"
                return result

            # Update DHIS2 org unit with OSID
            if self.update_org_unit_osid(org_unit_id, osid):
                result["status"] = "success"
                result["osid"] = osid
                logger.info(f"Synced {org_unit_name} -> osid={osid}")
            else:
                result["error"] = "Failed to update DHIS2"

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Error syncing {org_unit_name}: {e}")

        return result

    def run_sync(self, org_unit_ids: list[str] = None) -> SyncResult:
        """
        Run sync operation.

        Args:
            org_unit_ids: Optional list of specific org unit IDs to sync.
                         If None, syncs all pending org units.

        Returns:
            SyncResult with sync statistics.
        """
        result = SyncResult(
            success=False,
            started_at=datetime.now().isoformat(),
        )

        try:
            # Get Sunbird RC token
            logger.info("Authenticating with Sunbird RC...")
            self.get_sunbird_token()
            logger.info("Token acquired successfully")

            # Fetch org units to sync
            if org_unit_ids:
                logger.info(f"Fetching {len(org_unit_ids)} specific org units...")
                org_units = self.fetch_org_units_by_ids(org_unit_ids)
            else:
                logger.info("Fetching pending org units...")
                org_units = self.fetch_pending_org_units()

            logger.info(f"Found {len(org_units)} org units to sync")
            result.total = len(org_units)

            if not org_units:
                result.success = True
                result.finished_at = datetime.now().isoformat()
                return result

            # Sync each org unit
            for org_unit in org_units:
                sync_result = self.sync_single_org_unit(org_unit)
                result.results.append(sync_result)

                if sync_result["status"] == "success":
                    result.synced += 1
                else:
                    result.failed += 1

            result.success = result.failed == 0
            result.finished_at = datetime.now().isoformat()

        except Exception as e:
            logger.error(f"Sync failed: {e}")
            result.results.append({"error": str(e)})
            result.finished_at = datetime.now().isoformat()

        return result


# =============================================================================
# Factory Functions
# =============================================================================


def create_sync_engine(
    dhis2_url: str,
    dhis2_username: str,
    dhis2_password: str,
    sunbird_url: str,
    keycloak_url: str,
    client_id: str,
    client_secret: str,
    entity_mapping: dict,
    osid_attribute_id: str,
) -> OrgUnitSyncEngine:
    """Create an OrgUnitSyncEngine from configuration."""
    dhis2_config = DHIS2Config(
        base_url=dhis2_url,
        username=dhis2_username,
        password=dhis2_password,
    )

    sunbird_config = SunbirdConfig(
        base_url=sunbird_url,
        keycloak_url=keycloak_url,
        client_id=client_id,
        client_secret=client_secret,
    )

    mapping = EntityMapping(
        id=entity_mapping.get("id", ""),
        entity_type=entity_mapping.get("entityType", "WaterFacility"),
        org_unit_group_ids=entity_mapping.get("orgUnitGroupIds", []),
        field_mappings=entity_mapping.get("fieldMappings", []),
    )

    return OrgUnitSyncEngine(
        dhis2_config=dhis2_config,
        sunbird_config=sunbird_config,
        entity_mapping=mapping,
        osid_attribute_id=osid_attribute_id,
    )


def create_sync_engine_from_env(
    entity_mapping: dict,
    osid_attribute_id: str,
) -> OrgUnitSyncEngine:
    """Create an OrgUnitSyncEngine from environment variables."""
    import os

    return create_sync_engine(
        dhis2_url=os.environ.get("DHIS2_URL", "http://localhost:9090"),
        dhis2_username=os.environ.get("DHIS2_USERNAME", "admin"),
        dhis2_password=os.environ.get("DHIS2_PASSWORD", "district"),
        sunbird_url=os.environ.get("SUNBIRD_URL", "http://localhost:8081/api/v1"),
        keycloak_url=os.environ.get(
            "KEYCLOAK_URL",
            "http://keycloak:8080/auth/realms/sunbird-rc/protocol/openid-connect/token"
        ),
        client_id=os.environ.get("SUNBIRD_CLIENT_ID", "demo-api"),
        client_secret=os.environ.get("SUNBIRD_CLIENT_SECRET", ""),
        entity_mapping=entity_mapping,
        osid_attribute_id=osid_attribute_id,
    )
