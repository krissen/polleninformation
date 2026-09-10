# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Home Assistant custom integration (HACS) for monitoring pollen levels across Europe via the Austrian Pollen Information Service API. Supports 13 countries with multi-day forecasts and allergen-specific sensors.

## Development Commands

```bash
# Verify the tree is clean (run before committing or opening a PR)
make check

# Autofix formatting and whatever ruff can fix on its own
./scripts/lint.sh

# Validate Python syntax
python3 -m py_compile custom_components/polleninformation/<file>.py

# Validate JSON files
python3 -c "import json; json.load(open('custom_components/polleninformation/manifest.json'))"
```

Note: No build process - this is a pure Python Home Assistant integration.

## Quality Gates

Lint, format and secret-scanning run via [prek](https://github.com/j178/prek)
(`.pre-commit-config.yaml`), driven by a machine-global git hook dispatcher
rather than a per-repo `prek install`. Two things are required for it to run
at commit/push time, and both are repo-local (a fresh clone needs step 2
again):

```bash
# 1. the config already exists: .pre-commit-config.yaml
# 2. opt in for this clone
git config prek.enabled true
```

`SKIP_PREK=1 git commit ...` skips the lint pass for one commit without
disabling anything else. CI runs the same `.pre-commit-config.yaml` via
`prek run --all-files` (see `.github/workflows/test.yaml`), so there is one
rule list instead of two to keep in sync.

## Architecture

### Core Files (`custom_components/polleninformation/`)

- **`__init__.py`**: Integration setup and `PollenInformationDataUpdateCoordinator` for managing API polling (8-hour interval)
- **`api.py`**: Async HTTP client for the polleninformation.at API
- **`sensor.py`**: Three sensor types:
  - `PolleninformationSensor`: Per-allergen pollen levels (0-4 scale)
  - `AllergyRiskSensor`: Daily allergy risk with 4-day forecast
  - `AllergyRiskHourlySensor`: Hourly allergy risk
- **`config_flow.py`**: UI configuration flow
- **`const.py`**: Constants including supported countries/languages
- **`const_levels.py`**: Localized level names per language
- **`utils.py`**: Helper functions for normalization and country mapping

### Data Flow

1. User configures via UI (country, coordinates, API key)
2. Coordinator fetches from API every 8 hours
3. Sensors parse `contamination`, `allergyrisk`, and `allergyrisk_hourly` from response
4. Pollen levels: 0-4 (none/low/moderate/high/very high)
5. Allergy risk: 0-10 from API, scaled to 0-4 via `round(value / 2.5)`

### Scripts (`scripts/`)

Legacy helper scripts for API discovery and validation. Not actively maintained but useful for debugging:
- `test_pollenapi.py`: Single API call testing
- `test_pollenapi_countryid.py`: Country ID discovery
- `lint.sh`: Runs `ruff format . && ruff check . --fix` (uses `.venv/bin/ruff` when present)

## Commit Messages

Conventional Commits 1.0, with a mandatory scope: `type(scope): subject`.

- **type**: one of `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`,
  `build`, `ci`, `chore`, `revert`.
- **scope**: lowercase, short -- a filename without extension (`sensor`, not
  `sensor.py`) or a feature/module name (`config-flow`, `translations`).
- **subject**: imperative mood, lowercase first letter, no trailing period,
  <=72 characters.
- Breaking change: `type(scope)!: subject` plus a `BREAKING CHANGE:` footer.
- One commit per logical change; a fix touching several files for one bug is
  still one commit, two unrelated fixes are two commits.
- English only.
- **Never include references to Claude or other AI tools.**

Examples: `fix(sensor): correct forecast indexing`,
`chore(translations): remove verbose debug logging`.

## Key Guidelines

- **Translations**: Keep all `translations/*.json` files structurally complete (same keys as `en.json`). Translate where you can; use English as placeholder otherwise.
- **API Key Required**: Users must obtain their own key from polleninformation.at
- **Code Style**: Follow KISS/DRY principles; all comments in English
- **Dependencies**: Uses `aiohttp`, `async-timeout`, `Unidecode` (defined in manifest.json)
