# Changelog

## v0.5.1 — Configurable update interval and attribute fixes (unreleased)

### Bug fixes

- **`last_updated` attribute showed time-of-read** — was `datetime.now()` at
  attribute access, not the actual last API fetch time. Now sourced from the
  coordinator's fetch timestamp.

- **`update_success` attribute was misleading** — checked `data is not None`
  instead of the coordinator's actual `last_update_success` flag.

- **Timezone mismatch in `last_updated`** — `datetime.now()` returns naive UTC
  in containers. Now uses `dt_util.now()` for HA timezone-aware timestamps.
  The attribute returns a native `datetime` object (HA serializes to ISO 8601).

- **Options flow changes had no effect** — coordinator read country, latitude,
  longitude, language and API key from `entry.data` only. Changes made via
  Configure were stored in `entry.options` but never applied. Both coordinator
  and sensors now use options-over-data precedence.

- **Options flow defaults dropped on partial options** — `options or data`
  discarded all `entry.data` when any option existed. Replaced with dict merge
  (`{**data, **options}`) so all fields are always populated.

- **Missing `async_unload_entry`** — without proper unload, changing options
  could leave old coordinators and timers running. Added platform unload and
  coordinator cleanup. Update listener is now auto-removed via
  `entry.async_on_unload()`.

- **Coordinator missing `config_entry`** — `DataUpdateCoordinator.__init__()`
  was not passed the config entry, causing `ConfigEntryError` on newer HA
  versions.

- **`strings.json` completely outdated** — still referenced the legacy
  `conf_url`/`conf_city`/`conf_pollen` config flow, causing HA placeholder
  validation errors for all non-English translations.

- **Integration name in docs** — navigation instructions said "Pollen
  Information EU" but manifest uses "Polleninformation EU".

### New features

- **Configurable update interval** — users can now set the API polling interval
  (1–24 hours, default 8) via the integration options flow. Uses a
  `NumberSelector` with visible value, min/max and unit.

- **Manual refresh via `homeassistant.update_entity`** — documented the
  built-in service for on-demand data refresh in automations and scripts.

### Internal

- **Test suite** — 84 tests covering API client, coordinator, sensors, utility
  functions and const consistency. Uses `pytest-homeassistant-custom-component`.

- **Defensive interval validation** — persisted `update_interval` is cast,
  clamped to `[1, 24]` and falls back to default on corrupt values.

---

## v0.5.0-beta1 (2026-01-05)

### Bug fixes

- Fix allergen slug extraction for locations with underscores.
- Handle empty API data with stale attributes instead of marking sensors
  unavailable.
- Remove redundant `_attr_extra_state_attributes`.
- Remove API key from debug log statements.

### New features

- **API status page** — GitHub Actions workflow that checks API availability
  per country and publishes results to GitHub Pages with a shields.io badge.
- **Typed API exceptions** — `PollenApiAuthError`, `PollenApiConnectionError`
  and `PollenApiError` with proper handling in config flow and coordinator.
- **Error translations** — user-facing error messages for API exceptions in
  config flow.
- Validate API response structure before accepting data.

---

## v0.4.5 (2025-09-06)

### Bug fixes

- Fix sensor availability by implementing proper `CoordinatorEntity` pattern.

---

## v0.4.4 (2025-08-03)

### New features

- Expose raw allergy risk value (`numeric_state_raw` attribute).
- Add `level_raw` to allergy risk forecast entries.
- Hourly allergy risk sensor.
- Named state for `allergy_risk` sensor (was numeric only).
- Automatic cleanup of outdated sensors from entity registry.

### Bug fixes

- Rename "United Kingdom" to "Great Britain" to match API.
- Fix allergy risk forecast format.

---

## v0.4.3 (2025-07-18)

### New features

- Options flow for editing existing entries (country, location, language,
  API key).
- New allergen icon mappings.

### Housekeeping

- Remove unused `AIR_SENSOR_ICON_MAP` constant and air quality references.
- Mark legacy scripts as not actively maintained.

---

## v0.4.2 (2025-07-16)

### Bug fixes

- Release workflow fix.

---

## v0.4.1 (2025-07-16)

### Bug fixes

- Fix location slug generation (double fix).
- Correct translation keys.

---

## v0.4.0 (2025-07-16)

### New features

- **New API** — migrated to the current polleninformation.at public API.
- **Localized sensors** — sensor names and levels in the user's chosen
  language (16 languages supported).
- **Map-based location picker** — config flow uses HA's `LocationSelector`.
- **Multi-day forecast** — each sensor exposes a 4-day forecast attribute.
- **Suggested object IDs** — cleaner entity names.

### Housekeeping

- Translation files for all supported languages.
- Language map with latin allergen names.
- CONTRIBUTING.md.

---

## v0.3.1 (2025-07-12)

### Bug fixes

- Revert language-based sensor display name change that broke entity IDs.

---

## v0.3.0 (2025-07-10)

### New features

- Updated to new API endpoint (#2).
- HACS official listing.

---

## v0.2.5 (2025-06-30)

### Bug fixes

- Remove unsupported countries from HACS config.
- Run validation on releases.

---

## v0.2.4 (2025-06-10)

### Bug fixes

- Improved location slug to be closer to HA conventions.

---

## v0.2.1 (2025-06-09)

### Bug fixes

- Config flow fix.
- Requirements moved to manifest.
- Logo and validation fixes.

---

## v0.2.0 (2025-06-09)

### Bug fixes

- Better error handling during configuration.

---

## v0.1.0 (2025-06-08)

Initial release. Basic pollen sensor functionality using the
polleninformation.at API with support for multiple European countries.
