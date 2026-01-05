#!/usr/bin/env bash
set -e

cd "$(dirname "$0")/.."

# Aktivera venv
source .venv/bin/activate

# Fix för aiodns/c-ares DNS-timeout på macOS
# Tvingar användning av Google DNS istället för systemets resolver
export ARES_SERVERS="8.8.8.8,8.8.4.4"

# Starta Home Assistant
echo "Starting Home Assistant with DNS fix..."
hass --config "$PWD/config"
