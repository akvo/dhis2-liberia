# DHIS2 Custom Apps

This folder contains custom DHIS2 applications for the Liberia project.

## Quick Start

### Prerequisites
- Node.js 18+
- pnpm (`npm install -g pnpm`)

### Create a New App

```bash
cd apps
pnpm create @dhis2/app@latest my-app --yes
```

Options:
- `--yes` - Use defaults (TypeScript, pnpm, basic template)
- `--template react-router` - Add routing support

### Development

```bash
cd my-app
pnpm start --proxy http://localhost:9090
```

This starts a dev server at `http://localhost:3000` with hot reload.

### Build and Deploy

```bash
pnpm build
pnpm d2-app-scripts deploy http://localhost:9090 --username admin
```

Output:
- `build/app/` - Deployable app files
- `build/bundle/my-app-1.0.0.zip` - Installable package

---

## Project Structure

```
my-app/
├── src/
│   ├── App.tsx          # Main app component
│   └── components/      # React components
├── public/
│   └── dhis2-app-icon.png  # App icon (48x48 PNG)
├── d2.config.js         # DHIS2 app configuration
├── package.json
├── dev.sh               # Development script
└── build.sh             # Build and deploy script
```

### d2.config.js

```javascript
/** @type {import('@dhis2/cli-app-scripts').D2Config} */
const config = {
    type: 'app',
    title: 'My App',

    entryPoints: {
        app: './src/App.tsx',
    },
}

module.exports = config
```

### App Icon

Place your app icon in the `public` folder:

- **Filename**: `dhis2-app-icon.png` (exact name required)
- **Size**: 48x48 pixels
- **Format**: PNG with transparent background

```bash
# Resize an existing icon to 48x48
convert icon.png -resize 48x48 public/dhis2-app-icon.png
```

---

## App Runtime

The `@dhis2/app-runtime` library provides hooks for interacting with the DHIS2 API.

### useDataQuery

Fetch data from DHIS2:

```tsx
import { useDataQuery } from '@dhis2/app-runtime'

const query = {
    me: {
        resource: 'me',
    },
    orgUnits: {
        resource: 'organisationUnits',
        params: {
            paging: false,
            level: 1,
        },
    },
}

const MyComponent = () => {
    const { loading, error, data } = useDataQuery(query)

    if (loading) return <span>Loading...</span>
    if (error) return <span>Error: {error.message}</span>

    return <div>Hello {data.me.name}</div>
}
```

### useDataMutation

Create, update, or delete data:

```tsx
import { useDataMutation } from '@dhis2/app-runtime'

const mutation = {
    resource: 'dataValues',
    type: 'create',
    data: ({ value, dataElement, period, orgUnit }) => ({
        dataElement,
        period,
        orgUnit,
        value,
    }),
}

const MyComponent = () => {
    const [mutate, { loading, error }] = useDataMutation(mutation)

    const handleSubmit = async () => {
        await mutate({
            value: '100',
            dataElement: 'abc123',
            period: '202401',
            orgUnit: 'xyz789',
        })
    }

    return <button onClick={handleSubmit}>Save</button>
}
```

---

## UI Components

Import from `@dhis2/ui`:

```tsx
import {
    Button,
    Card,
    Input,
    Table,
    TableHead,
    TableBody,
    TableRow,
    TableCell,
    NoticeBox,
    Modal,
    ModalTitle,
    ModalContent,
    ModalActions,
} from '@dhis2/ui'
```

### Common Components

| Component | Usage |
|-----------|-------|
| `Button` | `<Button primary onClick={fn}>Save</Button>` |
| `Input` | `<Input value={val} onChange={fn} placeholder="..." />` |
| `Card` | `<Card><div>Content</div></Card>` |
| `NoticeBox` | `<NoticeBox title="Info">Message</NoticeBox>` |
| `Modal` | Dialog overlays for forms/confirmations |
| `DataTable` | Display structured data with sorting |
| `Select` | `<SingleSelect selected={val} onChange={fn}>...</SingleSelect>` |
| `Checkbox` | `<Checkbox checked={bool} onChange={fn} label="..." />` |
| `Switch` | `<Switch checked={bool} onChange={fn} label="..." />` |
| `Tabs` | `<TabBar><Tab>Tab 1</Tab></TabBar>` |
| `OrganisationUnitTree` | DHIS2 org unit hierarchy selector |
| `Transfer` | Multi-select with search |
| `AlertBar` | `<AlertBar duration={4000}>Saved!</AlertBar>` |
| `CircularLoader` | `<CircularLoader />` |

### Example: Form with Validation

```tsx
import { Button, Input, NoticeBox } from '@dhis2/ui'
import { useState } from 'react'

const MyForm = () => {
    const [name, setName] = useState('')
    const [error, setError] = useState('')

    const handleSubmit = () => {
        if (!name) {
            setError('Name is required')
            return
        }
        // Submit logic
    }

    return (
        <div>
            {error && <NoticeBox error title="Error">{error}</NoticeBox>}
            <Input
                label="Name"
                value={name}
                onChange={({ value }) => setName(value)}
            />
            <Button primary onClick={handleSubmit}>
                Submit
            </Button>
        </div>
    )
}
```

---

## Deployment

### Option 1: Using d2-app-scripts deploy (Recommended)

The official DHIS2 CLI deploy command:

```bash
# Build and deploy
pnpm build
export D2_PASSWORD=district
pnpm d2-app-scripts deploy http://localhost:9090 --username admin
```

Or use the `build.sh` script (reads credentials from `.env`):

```bash
./build.sh
```

### Option 2: Upload via App Management

1. Build the app: `pnpm build`
2. Go to DHIS2 > App Management
3. Upload `build/bundle/my-app-1.0.0.zip`

---

## Helper Scripts

Each app can include helper scripts:

### dev.sh

```bash
#!/bin/bash
# Reads DHIS2_PORT from ../../.env
source "../../.env"
pnpm start --proxy "http://localhost:${DHIS2_PORT:-8080}"
```

### build.sh

```bash
#!/bin/bash
# Reads credentials from ../../.env
source "../../.env"
pnpm build --force
export D2_PASSWORD="$DHIS2_PASSWORD"
pnpm d2-app-scripts deploy "http://localhost:${DHIS2_PORT}" --username "$DHIS2_USERNAME"
```

---

## Existing Apps

| App | Description |
|-----|-------------|
| `sunbird/` | Sunbird RC integration app |

---

## Resources

- [DHIS2 App Platform](https://developers.dhis2.org/docs/app-platform/getting-started)
- [DHIS2 App Runtime](https://developers.dhis2.org/docs/app-runtime/getting-started)
- [DHIS2 UI Components](https://ui.dhis2.nu/)
- [DHIS2 Web API](https://docs.dhis2.org/en/develop/using-the-api/dhis-core-version-master/metadata.html)
- [App Hub Guidelines](https://developers.dhis2.org/docs/guides/apphub-guidelines)
