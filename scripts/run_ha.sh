#!/usr/bin/env bash
set -e

cd "$(dirname "$0")/.."

# Activate virtual environment
source .venv/bin/activate

# Fix for aiodns/c-ares DNS timeout on macOS
# Forces use of Google DNS instead of the system resolver
export ARES_SERVERS="8.8.8.8,8.8.4.4"

# Start Home Assistant
echo "Starting Home Assistant with DNS fix..."
hass --config "$PWD/config"
