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

Wait 2-3 minutes for DHIS2 to initialize.

### 2. Setup DHIS2 Metadata

```bash
cd adapter

# Create org unit groups (BOREHOLE, HAND_PUMP, etc.) and OSID attribute
python -m cli.setup_metadata

# Import admin hierarchy (counties, districts, communities)
python -m cli.setup_admin_hierarchy --csv ../org_units_sample.csv --assign-user
```

### 3. Deploy Sunbird App

```bash
cd apps/sunbird
./build.sh
```

### 4. Configure via UI

Open http://localhost:9090/api/apps/sunbird/

1. **Settings** - Configure Sunbird RC connection:
   - Sunbird RC URL: `http://localhost:8081/api/v1`
   - Keycloak URL: `http://keycloak:8080/auth/realms/sunbird-rc/protocol/openid-connect/token`
   - Client ID: `demo-api`
   - Client Secret: `demo-api-secret-change-me`
   - OSID Attribute: Select `Sunbird OSID`

2. **Mappings** - Create entity mapping:
   - Select org unit groups (facility types)
   - Fetch Sunbird schema
   - Map DHIS2 fields to Sunbird fields

### 5. Create Test Facilities (Optional)

```bash
cd adapter

# Create random test facilities
python -m cli.create_random_facilities --count 20

# Or create a single facility
python -m cli.create_facility \
  --name "Test Borehole" \
  --parent-code LR_MON_GM_CT \
  --group BOREHOLE \
  --coordinates "[-10.79, 6.31]"
```

### 6. Sync

- Open the Sunbird App → **Sync** page
- Select entity mapping
- Click **Sync All Pending**

The worker (running via docker compose) will process the sync request.

## Project Structure

```
.
├── adapter/                    # Python sync service
│   ├── org_unit_worker.py     # Background worker (polls queue)
│   ├── org_unit_sync.py       # Sync engine
│   ├── cli/                   # CLI tools
│   │   ├── setup_metadata.py  # Setup org unit groups & attributes
│   │   ├── setup_admin_hierarchy.py  # Import org unit hierarchy
│   │   ├── create_facility.py        # Create single facility
│   │   ├── create_random_facilities.py  # Generate test data
│   │   └── import_facilities.py       # Bulk import from CSV
│   └── README.md              # Adapter documentation
├── apps/
│   └── sunbird/               # DHIS2 custom app
│       ├── src/               # React TypeScript source
│       └── build.sh           # Build & deploy script
├── docker-compose.yml
├── org_units_sample.csv       # Sample admin hierarchy
├── facilities_sample.csv      # Sample facilities for import
└── .env                       # Environment config
```

## Architecture

```
┌─────────────────┐      ┌──────────────────┐      ┌─────────────────────┐
│  DHIS2 App      │      │  DataStore       │      │  Worker             │
│  (Sunbird)      │      │                  │      │                     │
│                 │      │ sunbird-sync/    │      │ org_unit_worker.py  │
│  Settings       │──────│   config         │◄─────│                     │
│  Mappings       │write │   entity-mappings│poll  │        │            │
│  Sync           │──────│   queue          │      │        ▼            │
│  History        │◄─────│   history        │──────│   Sunbird RC        │
│                 │read  │   stats          │write │                     │
└─────────────────┘      └──────────────────┘      └─────────────────────┘
```

**Sync Flow:**
1. User clicks Sync in DHIS2 app
2. App queues request in DataStore
3. Worker polls queue, processes sync
4. Worker fetches org units (facilities) without OSID
5. Worker transforms data using field mappings
6. Worker POSTs to Sunbird RC (OAuth2 auth)
7. Worker updates org unit with OSID attribute
8. Results saved to history, displayed in app

## Configuration

### Environment Variables

Create `.env` from example:

```bash
cp .env.example .env
```

| Variable | Description | Default |
|----------|-------------|---------|
| `DHIS2_URL` | DHIS2 base URL | `http://localhost:9090` |
| `DHIS2_USERNAME` | DHIS2 admin username | `admin` |
| `DHIS2_PASSWORD` | DHIS2 admin password | `district` |
| `POLL_INTERVAL` | Worker poll interval (seconds) | `5` |

### DataStore Keys

The app stores configuration in DHIS2 DataStore namespace `sunbird-sync`:

| Key | Description |
|-----|-------------|
| `config` | Sunbird RC connection settings |
| `entity-mappings` | Org unit group → Sunbird entity mappings |
| `queue` | Pending sync requests |
| `history` | Sync results |
| `stats` | Sync statistics |

## CLI Reference

```bash
cd adapter

# Setup
python -m cli.setup_metadata                    # Create groups & attributes
python -m cli.setup_admin_hierarchy --csv FILE  # Import hierarchy

# Facilities
python -m cli.create_facility --name NAME --parent-code CODE --group GROUP
python -m cli.create_random_facilities --count N [--group GROUP]
python -m cli.import_facilities --csv FILE [--dry-run]

# Worker
python org_unit_worker.py --interval 5          # Run worker
python org_unit_worker.py --once                # Single sync cycle
```

## Troubleshooting

### Worker not processing

```bash
# Check worker logs
docker compose logs -f sunbird-worker

# Or run manually
cd adapter && python org_unit_worker.py --interval 5
```

### Sunbird RC 401 Unauthorized

- Use Docker hostname `keycloak:8080` not `localhost:8080`
- Check client secret matches Keycloak config

### Sunbird RC 500 Duplicate

- Facility with same coordinates/type/location exists
- Check if previous sync failed to save OSID to DHIS2

## Requirements

- Docker & Docker Compose
- Python 3.10+
- Node.js 18+ (for app development)
