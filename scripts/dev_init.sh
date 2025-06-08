#!/usr/bin/env bash
# scripts/dev_init.sh
# Körs med 'source scripts/dev_init.sh'

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  echo "❌ Kör med 'source scripts/dev_init.sh' – inte './scripts/dev_init.sh'"
  return 1
fi

BASEDIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/" && pwd)"

if [ -f "$BASEDIR/.venv/bin/activate" ]; then
  source "$BASEDIR/.venv/bin/activate"
else
  echo "❌ Kunde inte hitta .venv/. Kör först: ./setup.sh"
  return 1
fi

export PYTHONPATH="$BASEDIR/custom_components:$PYTHONPATH"
echo "✅ venv är aktiverad (för Home Assistant) och PYTHONPATH är satt."

