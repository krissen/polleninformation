#!/usr/bin/env bash
# Autofix helper: formats and fixes what ruff can fix on its own.
# This mutates files. To just verify the tree is clean (what CI and the
# commit/push hooks check), use `make check` instead.

set -e

cd "$(dirname "$0")/.."

ruff="ruff"
[ -x ".venv/bin/ruff" ] && ruff=".venv/bin/ruff"

"$ruff" format .
"$ruff" check . --fix
