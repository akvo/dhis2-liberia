# DHIS2 Liberia Project Context

## Project Overview

This project integrates DHIS2 with Sunbird RC for water facility registration in Liberia.

## Project Structure

```
dhis2-liberia/
├── adapter/           # Python sync scripts (DHIS2 ↔ Sunbird RC)
│   ├── sync.py       # Main sync script
│   ├── setup.py      # DHIS2 metadata setup
│   └── config.json   # Field mappings, attributes
├── apps/             # DHIS2 custom applications
│   └── sunbird/      # Sunbird sync management app
├── notebooks/        # Jupyter notebooks for testing
├── docs/             # Documentation
├── docker-compose.yml
├── dhis.conf         # DHIS2 configuration
└── .env              # Environment variables
```

## Key URLs & Ports

| Service | URL | Credentials |
|---------|-----|-------------|
| DHIS2 | http://localhost:9090 | admin / district |
| Sunbird RC | http://localhost:8081 | (via Keycloak) |
| Keycloak | http://keycloak:8080 | (OAuth2) |

## Sunbird Custom App (apps/sunbird/)

### Current Status
- [x] App scaffold created
- [x] Icon configured (public/dhis2-app-icon.png, 48x48)
- [x] Build/deploy scripts (build.sh, dev.sh)
- [ ] Phase 1: Navigation, pages, DataStore hooks
- [ ] Phase 2: Settings page (Route configuration)
- [ ] Phase 3: Sync page (pending TEIs, sync trigger)
- [ ] Phase 4: Dashboard & History

### Build & Deploy
```bash
cd apps/sunbird
./build.sh    # Build and deploy to DHIS2
./dev.sh      # Development with hot reload (has CORS issues)
```

### Architecture
- Uses DHIS2 Routes API for external calls (no credentials in browser)
- DataStore namespace: `sunbird-sync`
- Admin-only via custom authority: `SUNBIRD_ADMIN`

### GitHub Issue
See issue #1 for full implementation plan: https://github.com/akvo/dhis2-liberia/issues/1

## DHIS2 UI Components Reference

Import from `@dhis2/ui`:

### Navigation
```jsx
import { TabBar, Tab } from '@dhis2/ui'

<TabBar>
    <Tab selected={page === 'dashboard'} onClick={() => setPage('dashboard')}>Dashboard</Tab>
    <Tab selected={page === 'sync'} onClick={() => setPage('sync')}>Sync</Tab>
    <Tab selected={page === 'settings'} onClick={() => setPage('settings')}>Settings</Tab>
</TabBar>
```

### Data Table
```jsx
import { DataTable, DataTableHead, DataTableBody, DataTableRow,
         DataTableCell, DataTableColumnHeader } from '@dhis2/ui'

<DataTable>
    <DataTableHead>
        <DataTableRow>
            <DataTableColumnHeader>Name</DataTableColumnHeader>
            <DataTableColumnHeader>Status</DataTableColumnHeader>
        </DataTableRow>
    </DataTableHead>
    <DataTableBody>
        {items.map(item => (
            <DataTableRow key={item.id}>
                <DataTableCell>{item.name}</DataTableCell>
                <DataTableCell>{item.status}</DataTableCell>
            </DataTableRow>
        ))}
    </DataTableBody>
</DataTable>
```

### Forms (with react-final-form)
```jsx
import { InputFieldFF, CheckboxFieldFF, SingleSelectFieldFF,
         hasValue, email, composeValidators } from '@dhis2/ui'
import { Form, Field } from 'react-final-form'

<Form onSubmit={handleSubmit}>
    {({ handleSubmit }) => (
        <form onSubmit={handleSubmit}>
            <Field name="url" component={InputFieldFF} label="URL"
                   validate={composeValidators(hasValue, url)} />
            <Button type="submit" primary>Save</Button>
        </form>
    )}
</Form>
```

### Common Components
```jsx
import {
    Button,           // <Button primary onClick={fn}>Save</Button>
    Card,             // <Card><content /></Card>
    NoticeBox,        // <NoticeBox title="Info" warning>Message</NoticeBox>
    AlertBar,         // <AlertBar success duration={4000}>Saved!</AlertBar>
    Modal, ModalTitle, ModalContent, ModalActions,
    CircularLoader,   // <CircularLoader />
    Chip,             // <Chip>Label</Chip>
    Tag,              // <Tag positive>Success</Tag>
    Switch,           // <Switch checked={bool} onChange={fn} label="Enable" />
    Pagination,       // For paged data
    OrganisationUnitTree,  // DHIS2 org unit selector
} from '@dhis2/ui'
```

### Icons
```jsx
import { IconSync16, IconSettings24, IconCheckmark16, IconCross16,
         IconInfo16, IconWarning16, IconWorld24 } from '@dhis2/ui'
```

### Built-in Validators
- `hasValue` - Required field
- `email`, `url`, `number`, `integer`
- `createMinNumber(n)`, `createMaxNumber(n)`
- `createMinCharacterLength(n)`, `createMaxCharacterLength(n)`
- `createPattern(regex)`
- `composeValidators(v1, v2, ...)` - Combine validators

## DHIS2 App Runtime

### Data Queries
```jsx
import { useDataQuery } from '@dhis2/app-runtime'

const query = {
    me: { resource: 'me' },
    teis: {
        resource: 'trackedEntityInstances',
        params: ({ programId, status }) => ({
            program: programId,
            filter: `syncStatus:eq:${status}`,
            fields: '*',
            paging: false,
        }),
    },
}

const { loading, error, data, refetch } = useDataQuery(query, {
    variables: { programId: 'xxx', status: 'PENDING' }
})
```

### Data Mutations
```jsx
import { useDataMutation } from '@dhis2/app-runtime'

const mutation = {
    resource: 'dataStore/sunbird-sync/config',
    type: 'update',
    data: ({ config }) => config,
}

const [mutate, { loading }] = useDataMutation(mutation)
await mutate({ config: { routeId: 'xxx' } })
```

### DataStore Operations
```jsx
// Read
const query = {
    config: { resource: 'dataStore/sunbird-sync/config' }
}

// Create
const createMutation = {
    resource: 'dataStore/sunbird-sync/config',
    type: 'create',
    data: ({ config }) => config,
}

// Update
const updateMutation = {
    resource: 'dataStore/sunbird-sync/config',
    type: 'update',
    data: ({ config }) => config,
}
```

## DHIS2 Routes API (for external services)

Routes proxy external API calls through DHIS2 backend (avoids CORS, secures credentials).

### Create Route (admin)
```bash
POST /api/routes
{
    "name": "Sunbird RC API",
    "code": "sunbird-api",
    "url": "http://sunbird-rc:8081/api/v1/**",
    "auth": {
        "type": "oauth2-client-credentials",
        "clientId": "demo-api",
        "clientSecret": "secret"
    }
}
```

### Use Route (from app)
```jsx
const mutation = {
    resource: 'routes/ROUTE_ID/run',
    type: 'create',
    data: ({ payload }) => payload,
}
```

## Local Documentation References

- DHIS2 Developer Portal: `../../forks/developer-portal/docs/`
- DHIS2 UI Components: `../../forks/dhis2-ui/components/`
- App Implementation Plan: `apps/sunbird/IMPLEMENTATION_PLAN.md`

## Adapter (Python) - sync.py

The adapter syncs TEIs from DHIS2 to Sunbird RC:

1. Fetches TEIs with `syncStatus=PENDING`
2. Transforms to Sunbird RC format
3. POSTs to Sunbird RC (creates WaterFacility)
4. Updates DHIS2 TEI with `osid`, `wfId`, `syncStatus=SYNCED`

Key config files:
- `adapter/config.json` - Field mappings, attribute codes
- `.env` - Credentials, URLs
