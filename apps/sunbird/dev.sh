#!/bin/bash

# Sunbird DHIS2 App - Development Script
# This script starts the development server with hot reload

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/../../.env"

if [ -f "$ENV_FILE" ]; then
    source "$ENV_FILE"
fi

PROXY_URL="http://localhost:${DHIS2_PORT:-8080}"

echo "Starting Sunbird in development mode..."
echo "Proxying API requests to: $PROXY_URL"
echo "App will be available at: http://localhost:3000"
echo ""

pnpm start --proxy "$PROXY_URL"
