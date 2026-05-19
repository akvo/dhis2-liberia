#!/usr/bin/env bash
# Build and deploy the Sunbird DHIS2 Custom App using a node container.
# No local pnpm/node install required.
#
# Usage:
#   DHIS2_URL=https://demo1.akvotest.org \
#   DHIS2_USERNAME=admin \
#   DHIS2_PASSWORD='...' \
#     ./build-docker.sh
#
# Or via the parent .env file (DHIS2_PORT/DHIS2_USERNAME/DHIS2_PASSWORD) for
# the default localhost flow.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/../../.env"

if [ -f "$ENV_FILE" ]; then
    # shellcheck disable=SC1090
    source "$ENV_FILE"
fi

DHIS2_URL="${DHIS2_URL:-http://localhost:${DHIS2_PORT:-8080}}"
DHIS2_USER="${DHIS2_USERNAME:-admin}"
DHIS2_PASS="${DHIS2_PASSWORD:-district}"

NODE_IMAGE="${NODE_IMAGE:-node:24-alpine}"

# Named volumes for node_modules and build/ — keep the host source dir
# unmodified and cache pnpm install across runs. Set CLEAN=1 to nuke them.
NODE_MODULES_VOLUME="sunbird-app-node-modules"
BUILD_VOLUME="sunbird-app-build"
D2_VOLUME="sunbird-app-d2"
if [ "${CLEAN:-0}" = "1" ]; then
    docker volume rm "$NODE_MODULES_VOLUME" "$BUILD_VOLUME" "$D2_VOLUME" >/dev/null 2>&1 || true
fi

echo "Building & deploying Sunbird app -> $DHIS2_URL (user: $DHIS2_USER) via $NODE_IMAGE..."

# Pre-create mount points as the current user so docker doesn't create them
# as root-owned empty dirs on the host. Content lives in the named volumes;
# these host dirs stay empty and are git-ignored.
mkdir -p "$SCRIPT_DIR/node_modules" "$SCRIPT_DIR/build" "$SCRIPT_DIR/.d2"

# Runs as root inside container so corepack can symlink pnpm into
# /usr/local/bin. node_modules and build/ are isolated in named volumes so
# the host source tree stays clean.
docker run --rm \
    --network host \
    -v "$SCRIPT_DIR:/work" \
    -v "$NODE_MODULES_VOLUME:/work/node_modules" \
    -v "$BUILD_VOLUME:/work/build" \
    -v "$D2_VOLUME:/work/.d2" \
    -w /work \
    -e HOME=/tmp \
    -e XDG_DATA_HOME=/tmp/data \
    -e XDG_CACHE_HOME=/tmp/cache \
    -e PNPM_HOME=/tmp/pnpm \
    -e D2_PASSWORD="$DHIS2_PASS" \
    "$NODE_IMAGE" \
    sh -ec '
        corepack enable
        pnpm config set store-dir /tmp/pnpm-store
        pnpm install --frozen-lockfile
        pnpm build --force
        pnpm d2-app-scripts deploy "'"$DHIS2_URL"'" --username "'"$DHIS2_USER"'"
    '

echo
echo "Done. Open ${DHIS2_URL}/api/apps/sunbird/index.html"
