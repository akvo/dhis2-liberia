# DHIS2 ↔ Sunbird RC Integration Adapter

> **Status:** Implemented

## Overview

Adapter that syncs Water Facility Tracked Entity Instances (TEIs) from DHIS2 to Sunbird RC and updates DHIS2 with the generated IDs (`osid`, `wfId`).

## Files

| File | Purpose |
|------|---------|
| `dhis2_sunbird_adapter.py` | Main sync script (CLI) |
| `dhis2-sunbird-adapter.ipynb` | Interactive Jupyter notebook |
| `create_test_facility.py` | Create test TEI with syncStatus=PENDING |
| `adapter_config.json` | Field mappings & option value mappings |
| `.env` | Environment variables (URLs, credentials) |

## Quick Start

```bash
# Create a test facility
python create_test_facility.py

# Run sync
python dhis2_sunbird_adapter.py

# Or test connections first
python dhis2_sunbird_adapter.py --test-dhis2
python dhis2_sunbird_adapter.py --test-sunbird
```

## Architecture

```
DHIS2 (TEI with syncStatus=PENDING)
         │
         ▼
      Adapter Script
         │
         ├─ 1. Fetch pending records from DHIS2
         ├─ 2. Resolve org unit UIDs → names
         ├─ 3. Transform to Sunbird RC format
         ├─ 4. POST to Sunbird RC /api/v1/WaterFacility
         ├─ 5. GET generated osid & wfId
         └─ 6. Update DHIS2 with IDs + syncStatus=SYNCED
         │
         ▼
DHIS2 (Updated with osid, wfId, syncStatus=SYNCED)
```

## Configuration

All configuration is read from `.env` file:

```bash
# DHIS2
DHIS2_URL=http://localhost:9090/api
DHIS2_USERNAME=admin
DHIS2_PASSWORD=district

# Sunbird RC
SUNBIRD_URL=http://localhost:8081/api/v1
KEYCLOAK_URL=http://keycloak:8080/auth/realms/sunbird-rc/protocol/openid-connect/token
SUNBIRD_CLIENT_ID=demo-api
SUNBIRD_CLIENT_SECRET=your-secret-here
```

### DHIS2
- **Program:** `WF_REGISTRY`
- **Tracked Entity Type:** `WATER_FACILITY`

### DHIS2 Attribute Codes

IDs are fetched dynamically at runtime by code. The following attribute codes are used:

```
SUNBIRD_OSID, WF_ID, SYNC_STATUS_ATTR, GEO_CODE,
COUNTY, DISTRICT, COMMUNITY, WATER_POINT_TYPE_ATTR,
EXTRACTION_TYPE_ATTR, PUMP_TYPE_ATTR, NUM_TAPS,
HAS_DEPTH_INFO, DEPTH_METRES, INSTALLER, OWNER,
FUNDER, PHOTO_URL
```

> **Note:** IDs are fetched from DHIS2 at startup, so scripts work across different DHIS2 instances.

### Sunbird RC
- **Auth:** OAuth2 Bearer token via Keycloak (client_credentials grant)

## Field Mapping (DHIS2 → Sunbird RC)

| DHIS2 Attribute Code | DHIS2 Value Type | Sunbird RC Field | Notes |
|---------------------|------------------|------------------|-------|
| `GEO_CODE` | Text | `geoCode` | Direct mapping |
| `COUNTY` | Organisation Unit | `location.county` | Resolve UID → name |
| `DISTRICT` | Organisation Unit | `location.district` | Resolve UID → name |
| `COMMUNITY` | Organisation Unit | `location.community` | Resolve UID → name |
| TEI geometry | Point | `location.coordinates` | `{lat, lon}` |
| `WATER_POINT_TYPE_ATTR` | Option | `waterPointType` | Convert code → name |
| `EXTRACTION_TYPE_ATTR` | Option | `extractionType` | Convert code → name |
| `PUMP_TYPE_ATTR` | Option | `pumpType` | Convert code → name |
| `NUM_TAPS` | Integer | `numTaps` | Direct mapping |
| `HAS_DEPTH_INFO` | Boolean | `hasDepthInfo` | Direct mapping |
| `DEPTH_METRES` | Number | `depthMetres` | Direct mapping |
| `INSTALLER` | Option | `installer` | Convert code → name |
| `OWNER` | Option | `owner` | Convert code → name |
| `FUNDER` | Text | `funder` | Direct mapping |
| `PHOTO_URL` | URL | `photoUrl` | Direct mapping |

### Fields Updated After Sync (Sunbird RC → DHIS2)

| DHIS2 Attribute Code | Source |
|---------------------|--------|
| `SUNBIRD_OSID` | Sunbird RC response `osid` |
| `WF_ID` | Sunbird RC response `wfId` |
| `SYNC_STATUS_ATTR` | Set to `SYNC_STATUS_SYNCED` |

## Option Code Mapping

Option values in DHIS2 use prefixed codes (e.g., `WATER_POINT_TYPE_PDW`). Sunbird RC expects display names.

```python
WATER_POINT_TYPES = {
    "WATER_POINT_TYPE_PDW": "Protected dug well",
    "WATER_POINT_TYPE_UDW": "Unprotected dug well",
    "WATER_POINT_TYPE_TWB": "Tube well or borehole",
    "WATER_POINT_TYPE_PS": "Protected spring",
    "WATER_POINT_TYPE_US": "Unprotected spring",
    "WATER_POINT_TYPE_PWD": "Piped water into dwelling/plot/yard",
    "WATER_POINT_TYPE_PTS": "Public tap/standpipe",
    "WATER_POINT_TYPE_UEB": "Unequipped borehole",
    "WATER_POINT_TYPE_RWH": "Rainwater (harvesting)",
    "WATER_POINT_TYPE_SSD": "Sand/Sub-surface dam",
    "WATER_POINT_TYPE_OTH": "Other"
}

EXTRACTION_TYPES = {
    "EXTRACTION_TYPE_MANUAL": "Manual",
    "EXTRACTION_TYPE_ELECTRICAL": "Electrical",
    "EXTRACTION_TYPE_SOLAR": "Solar",
    "EXTRACTION_TYPE_OTHER": "Other"
}

PUMP_TYPES = {
    "PUMP_TYPE_AFRIDEV": "Afridev",
    "PUMP_TYPE_CONSALLEN": "Consallen",
    "PUMP_TYPE_INDIA_MARK": "India Mark",
    "PUMP_TYPE_KARDIA": "Kardia",
    "PUMP_TYPE_ROPE_PUMP": "Rope pump",
    "PUMP_TYPE_VERGNET": "Vergnet",
    "PUMP_TYPE_OTHER": "Other"
}

INSTALLER_TYPES = {
    "INSTALLER_TYPE_GOVERNMENT": "Government",
    "INSTALLER_TYPE_NGO": "NGO",
    "INSTALLER_TYPE_PRIVATE": "Private",
    "INSTALLER_TYPE_OTHER": "Other"
}

OWNER_TYPES = {
    "OWNER_TYPE_COMMUNITY": "Community",
    "OWNER_TYPE_PRIVATE_INDIVIDUAL": "Private Individual",
    "OWNER_TYPE_SCHOOL": "School",
    "OWNER_TYPE_NGO": "NGO",
    "OWNER_TYPE_HEALTH_FACILITY": "Health Facility",
    "OWNER_TYPE_OTHER_INSTITUTION": "Other institution",
    "OWNER_TYPE_CBO": "CBO",
    "OWNER_TYPE_PRIVATE": "Private",
    "OWNER_TYPE_UNKNOWN": "Unknown",
    "OWNER_TYPE_OTHER": "Other"
}
```

## Script Structure

```python
# dhis2_sunbird_adapter.py

# === Configuration ===
DHIS2_URL = "http://localhost:9090/api"
DHIS2_AUTH = ("admin", "district")

SUNBIRD_URL = "http://localhost:8081/api/v1"
KEYCLOAK_URL = "http://keycloak:8080/auth/realms/sunbird-rc/protocol/openid-connect/token"
CLIENT_ID = "demo-api"
CLIENT_SECRET = "55ce6b67-8bd6-4fe3-b1a7-94132e6cfb72"

# === Functions ===

def get_sunbird_token():
    """Get OAuth2 access token from Keycloak"""

def dhis2_get(endpoint):
    """GET request to DHIS2 API"""

def dhis2_put(endpoint, data):
    """PUT request to DHIS2 API"""

def sunbird_post(endpoint, data, token):
    """POST request to Sunbird RC API"""

def sunbird_get(endpoint, token):
    """GET request to Sunbird RC API"""

def resolve_org_unit(uid):
    """Convert org unit UID to name"""

def get_attribute_value(tei, attr_code):
    """Extract attribute value from TEI by code"""

def option_code_to_name(code, option_map):
    """Convert DHIS2 option code to display name"""

def fetch_pending_teis(program_id):
    """Fetch TEIs with syncStatus=PENDING"""

def transform_tei_to_sunbird(tei):
    """Transform DHIS2 TEI to Sunbird RC format"""

def sync_tei(tei, token):
    """Sync single TEI: create in Sunbird, update DHIS2"""

def run_sync():
    """Main sync function"""

# === Main ===
if __name__ == "__main__":
    run_sync()
```

## API Calls Reference

### DHIS2: Fetch Pending TEIs
```bash
GET /api/trackedEntityInstances
    ?ou=<ROOT_OU>
    &ouMode=DESCENDANTS
    &program=<PROGRAM_ID>
    &filter=<SYNC_STATUS_ATTR_ID>:eq:SYNC_STATUS_PENDING
    &fields=*
```

### DHIS2: Resolve Org Unit
```bash
GET /api/organisationUnits/<UID>?fields=name
```

### Sunbird RC: Create Water Facility
```bash
POST /api/v1/WaterFacility
Authorization: Bearer <token>
Content-Type: application/json

{
  "geoCode": "TEST001",
  "waterPointType": "Protected dug well",
  "location": {
    "county": "Montserrado County",
    "district": "Greater Monrovia District",
    "community": "Congo Town Clan",
    "coordinates": { "lat": 6.3156, "lon": -10.7957 }
  },
  "extractionType": "Manual",
  "pumpType": "Afridev",
  ...
}
```

### Sunbird RC: Get Facility (to retrieve wfId)
```bash
GET /api/v1/WaterFacility/<osid>
Authorization: Bearer <token>
```

### DHIS2: Update TEI with IDs
```bash
PUT /api/trackedEntityInstances/<TEI_ID>
{
  "attributes": [
    {"attribute": "<SUNBIRD_OSID_ID>", "value": "<osid>"},
    {"attribute": "<WF_ID_ID>", "value": "<wfId>"},
    {"attribute": "<SYNC_STATUS_ATTR_ID>", "value": "SYNC_STATUS_SYNCED"}
  ]
}
```

## Testing Steps

> **Note:** `python` command = Python 3

1. **Test DHIS2 connection:**
   ```bash
   python dhis2_sunbird_adapter.py --test-dhis2
   ```

2. **Test Sunbird RC connection:**
   ```bash
   python dhis2_sunbird_adapter.py --test-sunbird
   ```

3. **Run full sync:**
   ```bash
   python dhis2_sunbird_adapter.py
   ```

4. **Verify in DHIS2:**
   - TEI should have `osid`, `wfId` populated
   - `syncStatus` should be `SYNCED`

5. **Verify in Sunbird RC:**
   - Record should exist at `/api/v1/WaterFacility/<osid>`

## Error Handling

| Error | Action |
|-------|--------|
| DHIS2 connection failed | Exit with error message |
| Keycloak auth failed | Exit with error message |
| Sunbird RC create failed | Set `syncStatus=FAILED`, log error, continue |
| DHIS2 update failed | Log error, continue |
| Duplicate wfId (409/500) | Skip record (already synced), continue |

## Files Reference

| File | Purpose |
|------|---------|
| `dhis2_sunbird_adapter.py` | Main sync script (CLI) |
| `dhis2-sunbird-adapter.ipynb` | Interactive Jupyter notebook |
| `create_test_facility.py` | Create test TEI with syncStatus=PENDING |
| `dhis2-water-facility-setup.ipynb` | DHIS2 setup, contains attribute IDs |
| `DHIS2_WATER_FACILITY_SETUP.md` | Field mapping documentation |
