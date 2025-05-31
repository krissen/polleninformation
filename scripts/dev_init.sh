#!/usr/bin/env bash
#
# scripts/dev_init.sh
#
# Detta skript måste köras med 'source' så att venv-aktiveringen
# och miljövariablerna stannar kvar i samma shell-session.

# Kontrollera att skriptet sourcas
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  echo "❌ Detta skript måste köras med 'source scripts/dev_init.sh' – inte './scripts/dev_init.sh'"
  return 1
fi

# 1) Hitta projektets rot (antaget att script ligger i <root>/scripts)
BASEDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/" && pwd)"

# 2) Aktivera venv
if [ -f "$BASEDIR/.venv/bin/activate" ]; then
  source "$BASEDIR/.venv/bin/activate"
else
  echo "❌ Kunde inte hitta .venv/. Aktivera venv manuellt med:"
  echo "   python3.13 -m venv .venv"
  echo "   source .venv/bin/activate"
  return 1
fi

# 3) Sätt PYTHONPATH så HA hittar din custom_components
export PYTHONPATH="$BASEDIR/custom_components:$PYTHONPATH"

echo "✅  venv är aktiverad (för Home Assistant) och PYTHONPATH är satt."

# Nu är du redo att köra: hass --config "$BASEDIR/config"

