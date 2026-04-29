# DHIS2 Water Facility Registry - Liberia

Integration project for syncing Water Facility data between DHIS2 and Sunbird RC.

## Quick Start

### 1. Start Services

```bash
docker compose up -d
```

Services:
- **DHIS2**: http://localhost:9090 (admin/district)
- **Sunbird RC**: http://localhost:8081
- **Keycloak**: http://localhost:8080

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your credentials
```

### 3. Setup DHIS2

```bash
python adapter/setup.py
```

This creates:
- Option sets (Water Point Type, Extraction Type, etc.)
- Tracked entity attributes
- Water Facility tracked entity type
- Water Facility Registry program
- Organisation units (from org_units_sample.csv)
- Test facility with syncStatus=PENDING

### 4. Run Sync

```bash
# Sync pending facilities to Sunbird RC
python adapter/sync.py

# Test connections
python adapter/sync.py --test-dhis2
python adapter/sync.py --test-sunbird
```

## Project Structure

```
.
├── adapter/
│   ├── config.json         # Single source of truth for all config
│   ├── setup.py            # DHIS2 setup script
│   ├── sync.py             # DHIS2 ↔ Sunbird RC sync
│   └── create_facility.py  # Create test TEI
├── docs/                   # Documentation
├── docker-compose.yml
├── org_units_sample.csv    # Sample org units
├── .env                    # Environment config
└── .env.example
```

## Configuration

All configuration is in `adapter/config.json`:

- **option_sets**: Dropdown options (Water Point Type, Pump Type, etc.)
- **attributes**: Tracked entity attributes with types and option set links
- **field_mapping**: DHIS2 → Sunbird RC field mapping
- **sync_status**: Status values (PENDING, SYNCED, FAILED)
- **program**: Program metadata
- **tracked_entity_type**: TE type metadata

Environment variables in `.env`:

```bash
DHIS2_URL=http://localhost:9090/api
DHIS2_USERNAME=admin
DHIS2_PASSWORD=district

SUNBIRD_URL=http://localhost:8081/api/v1
KEYCLOAK_URL=http://keycloak:8080/auth/realms/sunbird-rc/protocol/openid-connect/token
SUNBIRD_CLIENT_ID=demo-api
SUNBIRD_CLIENT_SECRET=your-secret-here
```

## How It Works

```
DHIS2 (TEI with syncStatus=PENDING)
         │
         ▼
      adapter/sync.py
         │
         ├─ Fetch pending records
         ├─ Resolve org unit UIDs → names
         ├─ Transform to Sunbird RC format
         ├─ POST to Sunbird RC
         ├─ Get osid & wfId
         └─ Update DHIS2 (syncStatus=SYNCED)
         │
         ▼
DHIS2 (osid, wfId, syncStatus=SYNCED)
```

## Requirements

- Python 3.x
- Docker & Docker Compose
- Python packages: `requests`, `pandas`
