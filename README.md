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

Copy `.env.example` to `.env` and update credentials:

```bash
cp .env.example .env
```

### 3. Setup DHIS2 Water Facility Program

Run the setup notebook to create the Water Facility program, tracked entity type, and attributes:

```bash
cd notebooks
jupyter notebook dhis2-water-facility-setup.ipynb
```

### 4. Run the Sync Adapter

**Create a test facility:**
```bash
python adapter/create_facility.py
```

**Run sync:**
```bash
python adapter/sync.py
```

**Test connections:**
```bash
python adapter/sync.py --test-dhis2
python adapter/sync.py --test-sunbird
```

## Project Structure

```
.
├── adapter/                    # Sync adapter scripts
│   ├── sync.py                 # Main sync script
│   ├── create_facility.py      # Create test TEI
│   └── config.json             # Field & option mappings
├── notebooks/                  # Jupyter notebooks
│   ├── dhis2-water-facility-setup.ipynb
│   └── dhis2-sunbird-adapter.ipynb
├── docs/                       # Documentation
│   ├── DHIS2_WATER_FACILITY_SETUP.md
│   └── DHIS2_SUNBIRD_ADAPTER_PLAN.md
├── docker-compose.yml          # Docker services
├── .env                        # Environment config (not in git)
└── .env.example                # Example environment config
```

## How It Works

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

All configuration is stored in external files:

| File | Purpose |
|------|---------|
| `.env` | URLs and credentials (DHIS2, Sunbird RC, Keycloak) |
| `adapter/config.json` | Attribute codes, field mappings, option value mappings |

### Environment Variables (.env)

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

## Requirements

- Python 3.x
- Docker & Docker Compose
- Python packages: `requests`, `pandas` (for notebooks)

## Sync Status Values

| Status | Description |
|--------|-------------|
| `SYNC_STATUS_PENDING` | Ready to sync to Sunbird RC |
| `SYNC_STATUS_SYNCED` | Successfully synced |
| `SYNC_STATUS_FAILED` | Sync failed (retry with adapter) |
