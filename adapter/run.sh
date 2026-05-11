#!/bin/bash
set -e

echo "Installing dependencies..."
pip install --no-cache-dir -r requirements.txt

echo "Starting worker..."
exec python worker.py --interval "${POLL_INTERVAL:-5}"
