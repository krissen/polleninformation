#!/usr/bin/env bash
set -e

cd "$(dirname "$0")/.."

# Skapa venv om den inte finns
if [ ! -d ".venv" ]; then
  python3.13 -m venv .venv
fi

# Aktivera venv
source .venv/bin/activate

# Installera requirements
python3 -m pip install --upgrade pip
python3 -m pip install --requirement requirements.txt
python3 -m pip install mutagen home-assistant-frontend

# Sätt PYTHONPATH för HA custom_components
export PYTHONPATH="$PWD/custom_components:$PYTHONPATH"

echo "✅  venv is ready and requirements installed. PYTHONPATH set."
echo "Now start HA with: hass --config \"$PWD/config\""

