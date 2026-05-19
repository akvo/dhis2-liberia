# Acceptance Criteria: Pivot from TEI to Organisation Unit Architecture

## Context

Based on insights from DHIS2 experts in Africa, the current TEI-based approach for water facility registration should be refactored to use Organisation Units. In DHIS2, facilities (health facilities, schools, water points) are typically represented as org units in the hierarchy, not as Tracked Entity Instances.

**Current State:** Water facilities are TEIs enrolled in a program with attributes.

**Target State:** Water facilities ARE org units, categorized by Org Unit Groups, with OSID stored as a protected org unit attribute.

**Migration:** Fresh start (`docker compose down -v`) - no data migration needed.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        DHIS2                                    │
│                                                                 │
│  Organisation Unit Hierarchy          Org Unit Groups           │
│  ┌─────────────────────────┐         ┌───────────────────┐     │
│  │ Liberia (Level 1)       │         │ BOREHOLE          │     │
│  │ └── County (Level 2)    │         │ HAND_PUMP         │     │
│  │     └── District (L3)   │         │ PROTECTED_WELL    │     │
│  │         └── Community   │         │ PRIMARY_SCHOOL    │     │
│  │             ├── Fac A ──┼────────▶│ SECONDARY_SCHOOL  │     │
│  │             └── Fac B ──┼────────▶│                   │     │
│  └─────────────────────────┘         └───────────────────┘     │
│                                                                 │
│  Org Unit Attribute: SUNBIRD_OSID (system-managed)             │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ • Protected from user edits                              │   │
│  │ • Queryable: ?filter=SUNBIRD_OSID:null (pending)        │   │
│  │ • Queryable: ?filter=SUNBIRD_OSID:eq:abc123 (by OSID)   │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼ Sync via Routes API
┌─────────────────────────────────────────────────────────────────┐
│                      Sunbird RC (DPI Registry)                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Entity: WaterFacility                                    │   │
│  │   - osid: "abc123" ◀── Universal ID across all systems  │   │
│  │   - facilityName: "Borehole A"                          │   │
│  │   - location: { county, district, community, coords }   │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Key Mapping Concept

```
┌──────────────────────┐         ┌──────────────────────┐
│   Org Unit Group     │         │  Sunbird Entity Type │
├──────────────────────┤         ├──────────────────────┤
│ • BOREHOLE           │───┐     │                      │
│ • HAND_PUMP          │───┼────▶│   WaterFacility      │
│ • PROTECTED_WELL     │───┘     │                      │
├──────────────────────┤         ├──────────────────────┤
│ • PRIMARY_SCHOOL     │───┬────▶│   School             │
│ • SECONDARY_SCHOOL   │───┘     │                      │
└──────────────────────┘         └──────────────────────┘

Multiple Org Unit Groups can map to one Sunbird Entity Type
```

---

## Epic: Pivot Sunbird Sync to Organisation Unit Architecture

---

### User Story 1: Admin configures Sunbird connection

**As a** DHIS2 admin
**I want to** configure the connection to Sunbird RC
**So that** the system can authenticate and sync data

#### User Acceptance Criteria

| # | Criteria |
|---|----------|
| UAC-1.1 | Settings page shows connection fields: Sunbird RC URL, Keycloak URL, Client ID, Client Secret |
| UAC-1.2 | "Test Connection" button verifies credentials and shows success/error message |
| UAC-1.3 | Client Secret is masked in UI (password field) |
| UAC-1.4 | Connection status indicator shows connected/disconnected state |
| UAC-1.5 | Settings are persisted across sessions |

#### Technical Acceptance Criteria

| # | Criteria |
|---|----------|
| TAC-1.1 | Store config in DataStore: `sunbird-sync/config` |
| TAC-1.2 | Use DHIS2 Routes API for external calls (credentials stored in route, not browser) |
| TAC-1.3 | Test connection: call Keycloak token endpoint, then Sunbird health endpoint |
| TAC-1.4 | Route created via `/api/routes` with OAuth2 client credentials auth |

---

### User Story 2: Admin configures Entity Type mappings

**As a** DHIS2 admin
**I want to** map Org Unit Groups to Sunbird Entity Types
**So that** the system knows which facilities to sync and where

#### User Acceptance Criteria

| # | Criteria |
|---|----------|
| UAC-2.1 | "Entity Mappings" section shows list of configured mappings as cards/rows |
| UAC-2.2 | "Add Entity Mapping" button opens configuration modal/form |
| UAC-2.3 | Form includes: Entity Type name (text), Org Unit Groups (multi-select) |
| UAC-2.4 | Can select multiple Org Unit Groups for one Entity Type |
| UAC-2.5 | Can edit existing mappings |
| UAC-2.6 | Can delete mappings with confirmation dialog |
| UAC-2.7 | Preview shows count of org units matching selected groups |
| UAC-2.8 | Warning if an Org Unit Group is already assigned to another Entity Type |

#### Technical Acceptance Criteria

| # | Criteria |
|---|----------|
| TAC-2.1 | Fetch org unit groups via `/api/organisationUnitGroups?fields=id,name,code` |
| TAC-2.2 | Store mappings in DataStore: `sunbird-sync/entity-mappings` |
| TAC-2.3 | Mapping schema: `{id, entityType, orgUnitGroupIds[], fieldMappings[]}` |
| TAC-2.4 | Validate no org unit group assigned to multiple entity types |
| TAC-2.5 | Count preview: query org units with `filter=organisationUnitGroups.id:in:[ids]` |

---

### User Story 3: Admin configures Field Mappings per Entity Type

**As a** DHIS2 admin
**I want to** define how DHIS2 org unit fields map to Sunbird entity fields
**So that** data is correctly transformed during sync

#### User Acceptance Criteria

| # | Criteria |
|---|----------|
| UAC-3.1 | Each Entity Mapping has a "Field Mappings" section with a table |
| UAC-3.2 | Table columns: DHIS2 Source, Sunbird Target, Required (checkbox), Actions |
| UAC-3.3 | DHIS2 Source is a dropdown with available fields |
| UAC-3.4 | Sunbird Target is free text input for field path (e.g., "location.county") |
| UAC-3.5 | Can add, edit, remove field mappings |
| UAC-3.6 | "Preview" button shows sample transformation for one org unit |
| UAC-3.7 | Validation error if required Sunbird fields are not mapped |

#### Technical Acceptance Criteria

| # | Criteria |
|---|----------|
| TAC-3.1 | Source field options defined statically + dynamic org unit attributes |
| TAC-3.2 | Support dot notation for nested Sunbird fields: `location.coordinates` |
| TAC-3.3 | Support parent hierarchy syntax: `parent[level=2].name` |
| TAC-3.4 | Field mapping schema: `{source, target, required}` |
| TAC-3.5 | Preview fetches one sample org unit, applies transformation, shows JSON |

**Available DHIS2 Source Fields:**

| Source Field | Description | Example Value |
|--------------|-------------|---------------|
| `name` | Org unit display name | "Borehole ABC" |
| `code` | Org unit code | "BH_001" |
| `shortName` | Short name | "BH ABC" |
| `geometry.coordinates` | [longitude, latitude] | [-10.79, 6.31] |
| `openingDate` | Date established | "2024-01-15" |
| `parent.name` | Immediate parent name | "Community X" |
| `parent[level=2].name` | Ancestor at level 2 (County) | "Montserrado" |
| `parent[level=3].name` | Ancestor at level 3 (District) | "District A" |
| `parent[level=4].name` | Ancestor at level 4 (Community) | "Community X" |
| `attribute.{CODE}` | Custom attribute value | `attribute.FACILITY_STATUS` |

---

### User Story 4: Admin views facilities pending sync

**As a** DHIS2 admin
**I want to** see a list of facility org units that haven't been synced
**So that** I can review and initiate sync operations

#### User Acceptance Criteria

| # | Criteria |
|---|----------|
| UAC-4.1 | Sync page shows Entity Type selector dropdown |
| UAC-4.2 | Table shows facilities with columns: Name, Code, Location, Status |
| UAC-4.3 | Location shows hierarchy: County > District > Community |
| UAC-4.4 | Status shows: Pending (no OSID), Synced (has OSID) |
| UAC-4.5 | Status filter dropdown: All, Pending, Synced |
| UAC-4.6 | Default filter is "Pending" |
| UAC-4.7 | Search box filters by name or code |
| UAC-4.8 | Pagination with page size options (25, 50, 100) |
| UAC-4.9 | Total count displayed: "Showing 1-25 of 150 facilities" |

#### Technical Acceptance Criteria

| # | Criteria |
|---|----------|
| TAC-4.1 | Query by groups: `?filter=organisationUnitGroups.id:in:[ids]` |
| TAC-4.2 | Filter pending: `?filter=SUNBIRD_OSID:null` |
| TAC-4.3 | Filter synced: `?filter=SUNBIRD_OSID:!null` |
| TAC-4.4 | Fields: `id,name,code,geometry,ancestors[id,name,level],attributeValues` |
| TAC-4.5 | Server-side pagination with `page`, `pageSize` |
| TAC-4.6 | Create hook: `useFacilityOrgUnits(entityMappingId, status, search, page, pageSize)` |

---

### User Story 5: Admin syncs selected facilities

**As a** DHIS2 admin
**I want to** select specific facilities and sync them to Sunbird RC
**So that** I can control which facilities are registered

#### User Acceptance Criteria

| # | Criteria |
|---|----------|
| UAC-5.1 | Checkbox on each table row for selection |
| UAC-5.2 | "Select All" checkbox in header selects visible page |
| UAC-5.3 | Selection count shown: "3 selected" |
| UAC-5.4 | "Sync Selected" button enabled when items selected |
| UAC-5.5 | Confirmation dialog shows count and list of facility names |
| UAC-5.6 | Progress indicator during sync: "Syncing 3/10..." |
| UAC-5.7 | Success message with count after completion |
| UAC-5.8 | Failed items shown with error message |
| UAC-5.9 | Table refreshes to show updated sync status |

#### Technical Acceptance Criteria

| # | Criteria |
|---|----------|
| TAC-5.1 | Queue sync request to DataStore: `sunbird-sync/queue` |
| TAC-5.2 | Request schema: `{id, entityMappingId, orgUnitIds[], type: 'selected', status, createdAt}` |
| TAC-5.3 | Worker polls queue, processes requests |
| TAC-5.4 | Sync flow: fetch org unit → transform → POST to Sunbird → update OSID attribute |
| TAC-5.5 | Update OSID via: `PUT /api/organisationUnits/{id}` with attributeValues |
| TAC-5.6 | Write results to `sunbird-sync/history` |
| TAC-5.7 | Progress in `sunbird-sync/progress` for UI polling |

---

### User Story 6: Admin syncs all pending facilities

**As a** DHIS2 admin
**I want to** sync all pending facilities for an entity type in one action
**So that** I can efficiently register all new facilities

#### User Acceptance Criteria

| # | Criteria |
|---|----------|
| UAC-6.1 | "Sync All Pending" button visible on Sync page |
| UAC-6.2 | Button label shows count: "Sync All Pending (45)" |
| UAC-6.3 | Button disabled if no pending facilities |
| UAC-6.4 | Confirmation dialog shows total count |
| UAC-6.5 | Sync runs in background; admin can navigate away |
| UAC-6.6 | Progress bar shows overall progress |
| UAC-6.7 | Notification when complete |

#### Technical Acceptance Criteria

| # | Criteria |
|---|----------|
| TAC-6.1 | Queue request with `type: 'all'`, no `orgUnitIds` |
| TAC-6.2 | Worker fetches all pending org units for entity mapping |
| TAC-6.3 | Process in batches of 50 |
| TAC-6.4 | Continue on individual errors |
| TAC-6.5 | Update progress after each batch |

---

### User Story 7: Admin views sync history

**As a** DHIS2 admin
**I want to** see history of past sync operations
**So that** I can audit and troubleshoot

#### User Acceptance Criteria

| # | Criteria |
|---|----------|
| UAC-7.1 | History page shows list: Timestamp, Entity Type, Total, Success, Failed |
| UAC-7.2 | Clicking row expands to show individual results |
| UAC-7.3 | Failed items show error message |
| UAC-7.4 | "Retry Failed" button re-queues failed items |
| UAC-7.5 | Filter by Entity Type |
| UAC-7.6 | Filter by date range |

#### Technical Acceptance Criteria

| # | Criteria |
|---|----------|
| TAC-7.1 | History in DataStore: `sunbird-sync/history` as array |
| TAC-7.2 | Entry schema: `{id, timestamp, entityMappingId, totalCount, successCount, errorCount, results[]}` |
| TAC-7.3 | Result item: `{orgUnitId, orgUnitName, status, osid?, error?}` |
| TAC-7.4 | Retry creates new queue request with failed orgUnitIds |
| TAC-7.5 | Retain history for 90 days |

---

### User Story 8: Admin views dashboard

**As a** DHIS2 admin
**I want to** see overview statistics of sync status
**So that** I can monitor integration health

#### User Acceptance Criteria

| # | Criteria |
|---|----------|
| UAC-8.1 | Dashboard shows summary cards per Entity Type |
| UAC-8.2 | Each card shows: Total, Synced, Pending counts |
| UAC-8.3 | Clicking a card navigates to Sync page filtered by that entity |
| UAC-8.4 | Last sync timestamp shown per Entity Type |
| UAC-8.5 | Refresh button updates statistics |

#### Technical Acceptance Criteria

| # | Criteria |
|---|----------|
| TAC-8.1 | Total: count org units in mapped groups |
| TAC-8.2 | Synced: count with `SUNBIRD_OSID:!null` |
| TAC-8.3 | Pending: Total - Synced |
| TAC-8.4 | Cache stats in `sunbird-sync/stats` updated by worker |

---

## Adapter CLI Commands

### Command: `setup-metadata`

Sets up required DHIS2 metadata for org unit sync.

```bash
python -m adapter.cli setup-metadata
```

**Creates:**
1. Org Unit Attribute: `SUNBIRD_OSID`
2. Org Unit Groups: `BOREHOLE`, `HAND_PUMP`, `PROTECTED_WELL`, etc.
3. Org Unit Group Set: `WATER_FACILITY_TYPE` (optional)

#### Technical Acceptance Criteria

| # | Criteria |
|---|----------|
| TAC-CLI-1.1 | Create attribute via `/api/attributes` |
| TAC-CLI-1.2 | Attribute config: `{code: "SUNBIRD_OSID", name: "Sunbird OSID", valueType: "TEXT", organisationUnitAttribute: true}` |
| TAC-CLI-1.3 | Create org unit groups via `/api/organisationUnitGroups` |
| TAC-CLI-1.4 | Idempotent: skip if already exists |
| TAC-CLI-1.5 | Print summary of created/existing metadata |

---

### Command: `setup-admin-hierarchy`

Imports administrative org unit hierarchy from CSV.

```bash
python -m adapter.cli setup-admin-hierarchy --csv org_units_admin.csv
```

**CSV Format:**
```csv
name,shortName,code,parent_code,level
Liberia,Liberia,LR,,1
Montserrado,Montserrado,LR_MONT,LR,2
Greater Monrovia,Gr Monrovia,LR_MONT_GM,LR_MONT,3
Paynesville,Paynesville,LR_MONT_GM_PV,LR_MONT_GM,4
```

#### Technical Acceptance Criteria

| # | Criteria |
|---|----------|
| TAC-CLI-2.1 | Parse CSV with columns: name, shortName, code, parent_code, level |
| TAC-CLI-2.2 | Create org units via `/api/organisationUnits` |
| TAC-CLI-2.3 | Resolve parent by code lookup |
| TAC-CLI-2.4 | Process in level order (1, 2, 3, 4) to ensure parents exist |
| TAC-CLI-2.5 | Idempotent: skip if org unit with code exists |
| TAC-CLI-2.6 | Print summary: created/skipped counts |

---

### Command: `create-facility`

Creates a single facility org unit and assigns to group.

```bash
python -m adapter.cli create-facility \
  --name "Borehole ABC" \
  --short-name "BH ABC" \
  --code "BH_001" \
  --parent-code "LR_MONT_GM_PV" \
  --group "BOREHOLE" \
  --coordinates "[-10.79, 6.31]" \
  --opening-date "2024-01-15"
```

#### Technical Acceptance Criteria

| # | Criteria |
|---|----------|
| TAC-CLI-3.1 | Validate parent exists and is at community level (level 4) |
| TAC-CLI-3.2 | Validate group exists |
| TAC-CLI-3.3 | Create org unit with geometry if coordinates provided |
| TAC-CLI-3.4 | Add org unit to specified group via `/api/organisationUnitGroups/{id}/organisationUnits` |
| TAC-CLI-3.5 | Print created org unit ID and name |

---

### Command: `import-facilities`

Bulk import facilities from CSV.

```bash
python -m adapter.cli import-facilities --csv facilities.csv
```

**CSV Format:**
```csv
name,shortName,code,parent_code,group,longitude,latitude,opening_date
Borehole ABC,BH ABC,BH_001,LR_MONT_GM_PV,BOREHOLE,-10.79,6.31,2024-01-15
Hand Pump XYZ,HP XYZ,HP_001,LR_MONT_GM_PV,HAND_PUMP,-10.80,6.32,2024-01-20
```

#### Technical Acceptance Criteria

| # | Criteria |
|---|----------|
| TAC-CLI-4.1 | Parse CSV with facility columns |
| TAC-CLI-4.2 | Validate all parents exist before import |
| TAC-CLI-4.3 | Validate all groups exist before import |
| TAC-CLI-4.4 | Create facilities in batch |
| TAC-CLI-4.5 | Report: success count, error count, error details |

---

## DataStore Schema

```
sunbird-sync/
│
├── config
│   {
│     "sunbirdUrl": "https://sunbird-rc.example.com",
│     "keycloakUrl": "https://keycloak.example.com",
│     "clientId": "dhis2-sync",
│     "routeId": "route-sunbird-api"
│   }
│
├── entity-mappings
│   [
│     {
│       "id": "em-water-facility",
│       "entityType": "WaterFacility",
│       "orgUnitGroupIds": ["grp-borehole-id", "grp-handpump-id"],
│       "fieldMappings": [
│         {"source": "name", "target": "facilityName", "required": true},
│         {"source": "code", "target": "facilityCode", "required": false},
│         {"source": "geometry.coordinates", "target": "location.coordinates", "required": false},
│         {"source": "parent[level=2].name", "target": "location.county", "required": true},
│         {"source": "parent[level=3].name", "target": "location.district", "required": true},
│         {"source": "parent[level=4].name", "target": "location.community", "required": true}
│       ]
│     }
│   ]
│
├── queue
│   {
│     "requests": [
│       {
│         "id": "req-uuid",
│         "entityMappingId": "em-water-facility",
│         "orgUnitIds": ["ou-1", "ou-2"],
│         "type": "selected",
│         "status": "pending",
│         "createdAt": "2024-01-15T10:30:00Z"
│       }
│     ]
│   }
│
├── progress
│   {
│     "requestId": "req-uuid",
│     "current": 25,
│     "total": 100,
│     "status": "running"
│   }
│
├── history
│   [
│     {
│       "id": "hist-uuid",
│       "timestamp": "2024-01-15T10:35:00Z",
│       "entityMappingId": "em-water-facility",
│       "entityType": "WaterFacility",
│       "totalCount": 10,
│       "successCount": 9,
│       "errorCount": 1,
│       "results": [
│         {"orgUnitId": "ou-1", "orgUnitName": "Borehole A", "status": "success", "osid": "abc123"},
│         {"orgUnitId": "ou-2", "orgUnitName": "Pump B", "status": "error", "error": "Connection timeout"}
│       ]
│     }
│   ]
│
└── stats
    {
      "WaterFacility": {
        "total": 150,
        "synced": 120,
        "pending": 30,
        "lastSync": "2024-01-15T10:35:00Z"
      }
    }
```

---

## DHIS2 Metadata Created by CLI

```yaml
Attribute:
  - code: SUNBIRD_OSID
    name: Sunbird OSID
    shortName: OSID
    valueType: TEXT
    organisationUnitAttribute: true

OrganisationUnitGroup:
  - code: BOREHOLE
    name: Borehole
    shortName: Borehole
  - code: HAND_PUMP
    name: Hand Pump
    shortName: Hand Pump
  - code: PROTECTED_WELL
    name: Protected Well
    shortName: Protected Well

OrganisationUnitGroupSet (optional):
  - code: WATER_FACILITY_TYPE
    name: Water Facility Type
    organisationUnitGroups: [BOREHOLE, HAND_PUMP, PROTECTED_WELL]
```

---

## API Reference

```bash
# Get org unit groups
GET /api/organisationUnitGroups?fields=id,name,code&paging=false

# Get facilities by group (pending sync)
GET /api/organisationUnits?filter=organisationUnitGroups.id:in:[id1,id2]&filter=SUNBIRD_OSID:null&fields=id,name,code,geometry,ancestors[id,name,level],attributeValues&page=1&pageSize=25

# Get facilities by group (synced)
GET /api/organisationUnits?filter=organisationUnitGroups.id:in:[id1,id2]&filter=SUNBIRD_OSID:!null

# Find by OSID
GET /api/organisationUnits?filter=SUNBIRD_OSID:eq:abc123

# Update org unit with OSID after sync
PUT /api/organisationUnits/{id}
{
  "attributeValues": [
    {"attribute": {"id": "osid-attr-id"}, "value": "sunbird-osid-abc123"}
  ]
}

# Get org unit with ancestors (for hierarchy)
GET /api/organisationUnits/{id}?fields=id,name,ancestors[id,name,level]

# Add org unit to group
POST /api/organisationUnitGroups/{groupId}/organisationUnits/{ouId}
```

---

## File Changes Summary

### Remove (TEI-based code)

| File | Action |
|------|--------|
| `adapter/setup_config.json` | Replace with new schema |
| `adapter/cli/setup_facility.py` | Major refactor |
| `apps/sunbird/src/hooks/usePendingTeis.ts` | Delete |

### Modify

| File | Change |
|------|--------|
| `adapter/sync.py` | Replace TEI methods with org unit methods |
| `adapter/worker.py` | Update for new queue/entity mapping schema |
| `apps/sunbird/src/pages/Settings.tsx` | Add entity mapping + field mapping UI |
| `apps/sunbird/src/pages/Sync.tsx` | Update table for org units |
| `apps/sunbird/src/pages/Dashboard.tsx` | Update stats queries |
| `apps/sunbird/src/pages/History.tsx` | Minor updates |

### Add

| File | Purpose |
|------|---------|
| `adapter/cli/setup_metadata.py` | Create OSID attribute + groups |
| `adapter/cli/setup_admin_hierarchy.py` | Import admin org units from CSV |
| `adapter/cli/create_facility.py` | Create single facility |
| `adapter/cli/import_facilities.py` | Bulk import facilities |
| `adapter/transformer.py` | Field mapping transformation logic |
| `apps/sunbird/src/hooks/useFacilityOrgUnits.ts` | Query org units |
| `apps/sunbird/src/hooks/useEntityMappings.ts` | Entity mapping CRUD |
| `apps/sunbird/src/components/FieldMappingEditor.tsx` | Field mapping UI |

