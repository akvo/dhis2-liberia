# DHIS2 Sunbird RC Sync Adapter

Background worker service that syncs Tracked Entity Instances (TEIs) from DHIS2 to Sunbird RC.

## Architecture

```
┌─────────────────┐      ┌──────────────────┐      ┌─────────────┐
│  DHIS2 App      │      │  DataStore       │      │  Worker     │
│                 │      │                  │      │             │
│  Click "Sync"   │──────│ sunbird-sync/    │◄─────│  worker.py  │
│                 │write │   queue          │poll  │             │
│                 │      │   config         │      │      │      │
│  View results   │◄─────│   history        │──────│      ▼      │
│                 │read  │                  │write │ Sunbird RC  │
└─────────────────┘      └──────────────────┘      └─────────────┘
```

## Structure

```
adapter/
├── cli/                        # CLI tools for manual operations
│   ├── create_new_facility.py  # Create test TEIs
│   ├── setup_facility.py       # Setup DHIS2 metadata
│   └── sync_facility.py        # Manual sync CLI
├── worker.py                   # Polling service (main entry point)
├── sync.py                     # Core sync logic
├── setup_config.json           # Field mappings & attribute config
├── requirements.txt            # Python dependencies
├── run.sh                      # Docker entry script
├── Dockerfile                  # Container definition
└── README.md                   # This file
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

The worker reads Sunbird RC credentials from DHIS2 DataStore:

**Namespace:** `sunbird-sync`
**Key:** `config`

```json
{
  "sunbirdUrl": "http://sunbird-rc:8081/api/v1",
  "keycloakUrl": "http://keycloak:8080/auth/realms/sunbird-rc/protocol/openid-connect/token",
  "clientId": "demo-api",
  "clientSecret": "your-secret",
  "entityType": "WaterFacility",
  "programId": "bNDnlEUnzBL"
}
```

Configure these settings in the DHIS2 Sunbird App → Settings page.

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
python worker.py --interval 10
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
ExecStart=/usr/bin/python3 worker.py --interval 10
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

### Manual Sync

```bash
cd adapter
python cli/sync_facility.py
```

### Test Connections

```bash
# Test DHIS2
python cli/sync_facility.py --test-dhis2

# Test Sunbird RC
python cli/sync_facility.py --test-sunbird
```

### Create Test Data

```bash
python cli/create_new_facility.py --count 5
```

### Setup DHIS2 Metadata

```bash
python cli/setup_facility.py
```

## How It Works

1. **User clicks Sync** in DHIS2 Sunbird App
2. App writes request to `DataStore/sunbird-sync/queue`
3. **Worker polls** queue every N seconds
4. Worker reads **Sunbird config** from `DataStore/sunbird-sync/config`
5. Worker fetches **pending TEIs** from DHIS2
6. Worker **transforms** TEI data to Sunbird RC format
7. Worker **POSTs** to Sunbird RC API (with OAuth2 token)
8. Worker **updates TEI** in DHIS2 with `osid`, `wfId`, `syncStatus=SYNCED`
9. Worker writes **result** to `DataStore/sunbird-sync/history`
10. App displays result in History page

## Troubleshooting

### Worker not processing requests

1. Check worker logs: `docker-compose logs -f sunbird-worker`
2. Verify DHIS2 connection: `python cli/sync_facility.py --test-dhis2`
3. Check DataStore config has correct URLs

### Sunbird RC 401 Unauthorized

Token issuer mismatch. Ensure:
- `keycloakUrl` uses hostname that Sunbird RC expects (e.g., `keycloak:8080` not `localhost:8080`)
- If running outside Docker, add `keycloak` to `/etc/hosts`

### Sunbird RC 404 Not Found

- Check `sunbirdUrl` has no trailing spaces
- Verify `entityType` matches Sunbird RC schema (e.g., `WaterFacility`)

## Development

```bash
# Run worker with verbose logging
python worker.py --interval 5

# Run single sync cycle (for cron)
python worker.py --once
```
