# DHIS2 Sunbird RC Sync Adapter

Background worker service that syncs Organisation Units (facilities) from DHIS2 to Sunbird RC.

## Architecture

```
┌─────────────────┐      ┌──────────────────┐      ┌─────────────────────┐
│  DHIS2 App      │      │  DataStore       │      │  Worker             │
│                 │      │                  │      │                     │
│  Click "Sync"   │──────│ sunbird-sync/    │◄─────│ org_unit_worker.py  │
│                 │write │   queue          │poll  │                     │
│                 │      │   config         │      │        │            │
│  View results   │◄─────│   history        │──────│        ▼            │
│                 │read  │   entity-mappings│write │   Sunbird RC        │
└─────────────────┘      └──────────────────┘      └─────────────────────┘
```

## Structure

```
adapter/
├── cli/                            # CLI tools
│   ├── create_facility.py          # Create single facility
│   ├── create_random_facilities.py # Generate test data
│   ├── import_facilities.py        # Bulk import from CSV
│   ├── setup_admin_hierarchy.py    # Setup org unit hierarchy
│   └── setup_metadata.py           # Setup DHIS2 metadata
├── org_unit_worker.py              # Polling service (main entry point)
├── org_unit_sync.py                # Core sync logic
├── setup_config.json               # Metadata setup config
├── requirements.txt                # Python dependencies
├── run.sh                          # Docker entry script
├── Dockerfile                      # Container definition
└── README.md                       # This file
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DHIS2_URL` | DHIS2 base URL | `http://localhost:9090` |
| `DHIS2_USERNAME` | DHIS2 admin username | `admin` |
| `DHIS2_PASSWORD` | DHIS2 admin password | `district` |
| `POLL_INTERVAL` | Queue poll interval (seconds) | `5` |

### DataStore Configuration

The worker reads configuration from DHIS2 DataStore:

**Namespace:** `sunbird-sync`

**Key: `config`** - Sunbird RC connection settings
```json
{
  "sunbirdUrl": "http://sunbird-rc:8081/api/v1",
  "keycloakUrl": "http://keycloak:8080/auth/realms/sunbird-rc/protocol/openid-connect/token",
  "clientId": "demo-api",
  "clientSecret": "your-secret",
  "osidAttributeId": "abc123xyz"
}
```

**Key: `entity-mappings`** - Maps org unit groups to Sunbird entity types
```json
[
  {
    "id": "em-123",
    "entityType": "WaterFacility",
    "orgUnitGroupIds": ["ST3I7msiaGu", "NJylpVluVYv"],
    "fieldMappings": [
      {"source": "name", "target": "facilityName"},
      {"source": "geometry.coordinates[1]", "target": "location.coordinates.lat"},
      {"source": "geometry.coordinates[0]", "target": "location.coordinates.lon"}
    ]
  }
]
```

Configure these in the DHIS2 Sunbird App → Settings and Mappings pages.

## Deployment

### Option 1: Docker Compose (Recommended)

Add to your `docker-compose.yml`:

```yaml
services:
  sunbird-worker:
    build: ./adapter
    environment:
      - DHIS2_URL=http://dhis2-core:8080
      - DHIS2_USERNAME=admin
      - DHIS2_PASSWORD=district
      - POLL_INTERVAL=10
    depends_on:
      - dhis2-core
    restart: unless-stopped
```

Then run:

```bash
docker-compose up -d sunbird-worker
```

### Option 2: Manual / VM Deployment

```bash
cd adapter
pip install -r requirements.txt
python org_unit_worker.py --interval 10
```

### Option 3: Systemd Service

Create `/etc/systemd/system/sunbird-worker.service`:

```ini
[Unit]
Description=DHIS2 Sunbird RC Sync Worker
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/dhis2-liberia/adapter
Environment=DHIS2_URL=http://localhost:9090
Environment=DHIS2_USERNAME=admin
Environment=DHIS2_PASSWORD=district
ExecStart=/usr/bin/python3 org_unit_worker.py --interval 10
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable sunbird-worker
sudo systemctl start sunbird-worker
```

## CLI Tools

### Create Single Facility

```bash
python -m adapter.cli.create_facility \
  --name "Borehole ABC" \
  --parent-code LR_MON_GM_CT \
  --group BOREHOLE \
  --coordinates "[-10.79, 6.31]"
```

### Create Random Test Facilities

```bash
# Create 50 random facilities
python -m adapter.cli.create_random_facilities --count 50

# Create 100 boreholes only
python -m adapter.cli.create_random_facilities --count 100 --group BOREHOLE
```

### Bulk Import from CSV

```bash
# Validate first
python -m adapter.cli.import_facilities --csv facilities.csv --dry-run

# Import
python -m adapter.cli.import_facilities --csv facilities.csv
```

CSV format:
```csv
name,short_name,code,parent_code,group,longitude,latitude,opening_date
Borehole ABC,BH ABC,BH_001,LR_MON_GM_CT,BOREHOLE,-10.79,6.31,2024-01-15
```

### Setup DHIS2 Metadata

```bash
# Setup org unit groups and attributes
python -m adapter.cli.setup_metadata

# Setup admin hierarchy from CSV
python -m adapter.cli.setup_admin_hierarchy --csv org_units.csv
```

## How It Works

1. **User clicks Sync** in DHIS2 Sunbird App
2. App writes request to `DataStore/sunbird-sync/queue`
3. **Worker polls** queue every N seconds
4. Worker reads **config** and **entity mappings** from DataStore
5. Worker fetches **org units** without OSID from mapped groups
6. Worker **transforms** org unit data using field mappings
7. Worker **POSTs** to Sunbird RC API (with OAuth2 token)
8. Worker **updates org unit** in DHIS2 with OSID attribute
9. Worker writes **result** to `DataStore/sunbird-sync/history`
10. App displays result in History page

## Troubleshooting

### Worker not processing requests

1. Check worker logs: `docker-compose logs -f sunbird-worker`
2. Verify config: Check DataStore `sunbird-sync/config` has all required fields
3. Check entity mappings exist in `sunbird-sync/entity-mappings`

### Sunbird RC 401 Unauthorized

Token issuer mismatch. Ensure:
- `keycloakUrl` uses hostname that Sunbird RC expects (e.g., `keycloak:8080` not `localhost:8080`)
- If running outside Docker, add `keycloak` to `/etc/hosts`

### Sunbird RC 400 Bad Request

- Check field mappings match Sunbird RC schema
- Verify required fields are mapped
- Use the Mappings page to fetch schema and see required fields

### Sunbird RC 500 Duplicate Error

- Facility with same coordinates/type/location already exists in Sunbird
- Check if facility was previously synced but OSID not saved to DHIS2

### DHIS2 OSID Update Fails

- Verify `osidAttributeId` in config matches actual attribute ID
- Check attribute has `organisationUnitAttribute: true`

## Development

```bash
# Run worker with verbose logging
python org_unit_worker.py --interval 5

# Run single sync cycle (for cron)
python org_unit_worker.py --once
```
