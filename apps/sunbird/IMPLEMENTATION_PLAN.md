# Sunbird App Implementation Plan

## Overview

Transform the Sunbird DHIS2 app into a full sync management tool that:
1. Configures connection to Sunbird RC via DHIS2 Routes (secure, no credentials in browser)
2. Views pending TEIs and sync status
3. Manually triggers sync operations
4. Displays sync history and logs

## Architecture

### Security Model (Per DHIS2 Guidelines)

```
Browser App ──> DHIS2 Routes API ──> Sunbird RC / Keycloak
                    │
                    └── Credentials stored encrypted in DHIS2
                        (never exposed to browser)
```

**Key Principles:**
- No credentials in browser code or DataStore
- Use DHIS2 Routes for all external API calls
- Routes handle OAuth2 token exchange with Keycloak
- Admin-only access via DHIS2 authorities

### Routes Configuration

Two routes needed:

1. **Keycloak Token Route** (`sunbird-auth`)
   - URL: `{KEYCLOAK_URL}/protocol/openid-connect/token`
   - Auth: `oauth2-client-credentials`
   - Purpose: Get access token for Sunbird RC

2. **Sunbird RC API Route** (`sunbird-api`)
   - URL: `{SUNBIRD_URL}/api/v1/**`
   - Auth: Uses token from route 1
   - Purpose: Proxy all Sunbird RC API calls

### DataStore Structure

Namespace: `sunbird-sync` (reserved in d2.config.js)

```json
{
  "config": {
    "routeIds": {
      "auth": "route-id-for-keycloak",
      "api": "route-id-for-sunbird-api"
    },
    "programCode": "WF_PROGRAM",
    "fieldMapping": { ... }
  },
  "syncHistory": [
    {
      "timestamp": "2026-05-06T10:00:00Z",
      "totalRecords": 10,
      "successful": 9,
      "failed": 1,
      "details": [...]
    }
  ]
}
```

## App Structure

```
sunbird/
├── src/
│   ├── App.tsx                     # Main app with navigation
│   ├── pages/
│   │   ├── Dashboard.tsx           # Overview, stats, quick actions
│   │   ├── Settings.tsx            # Route configuration
│   │   ├── Sync.tsx                # View pending, trigger sync
│   │   └── History.tsx             # Sync logs
│   ├── components/
│   │   ├── Navigation.tsx          # Sidebar/tabs navigation
│   │   ├── PendingTable.tsx        # Table of pending TEIs
│   │   ├── SyncProgress.tsx        # Progress bar during sync
│   │   ├── RouteSetup.tsx          # Form to configure routes
│   │   └── SyncLogEntry.tsx        # Single sync log item
│   ├── hooks/
│   │   ├── useConfig.ts            # Read/write DataStore config
│   │   ├── usePendingTeis.ts       # Fetch pending TEIs
│   │   ├── useSyncHistory.ts       # Fetch sync logs
│   │   └── useRouteApi.ts          # Call external APIs via Routes
│   └── lib/
│       ├── transformer.ts          # TEI → Sunbird format
│       ├── constants.ts            # Field mappings, status codes
│       └── types.ts                # TypeScript interfaces
├── public/
│   └── dhis2-app-icon.png
└── d2.config.js                    # With dataStoreNamespace
```

## Implementation Phases

### Phase 1: Foundation
- [ ] Update d2.config.js with dataStoreNamespace
- [ ] Create page components (Dashboard, Settings, Sync, History)
- [ ] Add navigation (tabs or sidebar)
- [ ] Create useConfig hook for DataStore

### Phase 2: Settings Page
- [ ] Create RouteSetup component
- [ ] Form to input/select Route IDs
- [ ] Test connection button (calls route to verify)
- [ ] Save config to DataStore

### Phase 3: Sync Page
- [ ] Create usePendingTeis hook
- [ ] Display pending TEIs in table
- [ ] "Sync All" and "Sync Selected" buttons
- [ ] Progress indicator during sync
- [ ] Update TEI status after sync

### Phase 4: Dashboard & History
- [ ] Show stats: pending count, last sync, success rate
- [ ] Sync history list with expandable details
- [ ] Quick "Sync Now" button

## d2.config.js Updates

```javascript
/** @type {import('@dhis2/cli-app-scripts').D2Config} */
const config = {
    type: 'app',
    title: 'Sunbird',

    // Reserve DataStore namespace
    dataStoreNamespace: 'sunbird-sync',

    // Admin-only access
    customAuthorities: ['SUNBIRD_ADMIN'],

    entryPoints: {
        app: './src/App.tsx',
    },
}

module.exports = config
```

## UI Wireframes

### Dashboard
```
┌─────────────────────────────────────────────────────┐
│  Sunbird Sync                    [Settings] [Help]  │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐            │
│  │ Pending  │ │ Synced   │ │ Failed   │            │
│  │    15    │ │   234    │ │    3     │            │
│  └──────────┘ └──────────┘ └──────────┘            │
│                                                     │
│  Last Sync: 2026-05-06 10:30 AM                    │
│  ┌─────────────────────────────────────┐           │
│  │        [Sync Pending Records]       │           │
│  └─────────────────────────────────────┘           │
│                                                     │
│  Recent Activity                                    │
│  ─────────────────                                  │
│  • 10:30 - Synced 5 records (5 success, 0 failed)  │
│  • 09:15 - Synced 8 records (7 success, 1 failed)  │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### Settings
```
┌─────────────────────────────────────────────────────┐
│  Settings                                           │
├─────────────────────────────────────────────────────┤
│                                                     │
│  Sunbird RC Connection                              │
│  ─────────────────────                              │
│                                                     │
│  Authentication Route ID:                           │
│  ┌───────────────────────────────────────┐         │
│  │ [Select or enter Route ID]            │         │
│  └───────────────────────────────────────┘         │
│                                                     │
│  API Route ID:                                      │
│  ┌───────────────────────────────────────┐         │
│  │ [Select or enter Route ID]            │         │
│  └───────────────────────────────────────┘         │
│                                                     │
│  [Test Connection]  [Save Settings]                 │
│                                                     │
│  ℹ️ Routes must be configured in DHIS2 Route       │
│     Manager by a system administrator.             │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### Sync Page
```
┌─────────────────────────────────────────────────────┐
│  Sync Records                    [⟳ Refresh]        │
├─────────────────────────────────────────────────────┤
│                                                     │
│  Pending Records (15)           [Sync Selected]     │
│  ─────────────────────────────────────────────────  │
│  ☐ │ GeoCode    │ County   │ District │ Status     │
│  ──┼────────────┼──────────┼──────────┼──────────  │
│  ☑ │ WF-001     │ Bong     │ Jorquell │ PENDING    │
│  ☑ │ WF-002     │ Lofa     │ Foya     │ PENDING    │
│  ☐ │ WF-003     │ Nimba    │ Sanniqui │ PENDING    │
│                                                     │
│  ──────────────────────────────────────────────────│
│  ┌─────────────────────────────────────┐           │
│  │         [Sync All Records]          │           │
│  └─────────────────────────────────────┘           │
│                                                     │
└─────────────────────────────────────────────────────┘
```

## Setup Instructions for Admin

### 1. Create Routes in DHIS2

Using Route Manager App or API:

**Keycloak Auth Route:**
```json
{
  "name": "Sunbird Keycloak Auth",
  "code": "sunbird-auth",
  "url": "http://keycloak:8080/auth/realms/sunbird-rc/protocol/openid-connect/token",
  "auth": {
    "type": "oauth2-client-credentials",
    "clientId": "demo-api",
    "clientSecret": "your-secret-here"
  }
}
```

**Sunbird API Route:**
```json
{
  "name": "Sunbird RC API",
  "code": "sunbird-api",
  "url": "http://sunbird-rc:8081/api/v1/**",
  "auth": {
    "type": "api-headers",
    "headers": {
      "Authorization": "Bearer ${token}"
    }
  }
}
```

### 2. Configure in Sunbird App

1. Open Sunbird app in DHIS2
2. Go to Settings
3. Select the Route IDs created above
4. Test connection
5. Save

### 3. Grant Access

Assign `SUNBIRD_ADMIN` authority to users who should manage sync.

## Questions to Resolve

1. **Route Manager App**: Is it installed? (Needed for admin to create routes)
2. **OAuth2 Flow**: Does DHIS2 Routes support chained auth (get token, then use it)?
3. **Batch Size**: How many TEIs to sync per batch? (Recommend 10-20)

## Next Steps

1. Review this plan
2. Decide on navigation style (tabs vs sidebar)
3. Confirm Routes can handle the OAuth2 flow
4. Begin Phase 1 implementation
