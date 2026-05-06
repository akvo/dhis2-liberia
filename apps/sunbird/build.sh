#!/bin/bash

# Sunbird DHIS2 App - Build Script

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/../../.env"

if [ -f "$ENV_FILE" ]; then
    source "$ENV_FILE"
fi

DHIS2_URL="http://localhost:${DHIS2_PORT:-8080}"
DHIS2_USER="${DHIS2_USERNAME:-admin}"
DHIS2_PASS="${DHIS2_PASSWORD:-district}"

cd "$SCRIPT_DIR"

echo "Building Sunbird..."
pnpm build --force

echo "Deploying to DHIS2..."
export D2_PASSWORD="$DHIS2_PASS"
pnpm d2-app-scripts deploy "$DHIS2_URL" --username "$DHIS2_USER"

echo ""
echo "Done! Open $DHIS2_URL/api/apps/sunbird/index.html"
