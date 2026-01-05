# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Home Assistant custom integration (HACS) for monitoring pollen levels across Europe via the Austrian Pollen Information Service API. Supports 13 countries with multi-day forecasts and allergen-specific sensors.

## Development Commands

```bash
# Lint and format (always run before committing)
./scripts/lint.sh

# Validate Python syntax
python3 -m py_compile custom_components/polleninformation/<file>.py

# Validate JSON files
python3 -c "import json; json.load(open('custom_components/polleninformation/manifest.json'))"
```

Note: No build process - this is a pure Python Home Assistant integration.

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
- `lint.sh`: Runs `ruff format . && ruff check . --fix`

## Commit Messages

Format: `(scope) Beskrivning`

- **Single file**: Use filename (can be abbreviated), e.g. `(sensor.py) Fix forecast indexing`
- **Multiple files**: Use action/feature name, e.g. `(debug messages) Remove verbose logging`
- **Never include references to Claude or other AI tools**

## Key Guidelines

- **Translations**: Only modify `translations/en.json` - other languages are handled separately
- **API Key Required**: Users must obtain their own key from polleninformation.at
- **Code Style**: Follow KISS/DRY principles; all comments in English
- **Dependencies**: Uses `aiohttp`, `async-timeout`, `Unidecode` (defined in manifest.json)
