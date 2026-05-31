# Changelog

## v0.5.2 (unreleased)

### Bug fixes

- **Broken logo on the API status page** — the page hot-linked the
  Polleninformation logo from polleninformation.at, whose asset path changed
  (cache-busting hash), breaking the image. The logo is now vendored locally
  under `docs/` and referenced relatively, so the status page no longer depends
  on their site.

### Internal

- **CI: bump first-party GitHub Actions to Node 24 majors** — `actions/checkout`
  → v5, `actions/setup-python` → v6, `actions/upload-pages-artifact` → v5,
  `actions/deploy-pages` → v5. Drops the Node.js 20 runtime deprecation ahead of
  GitHub's forced Node 24 cutover (2026-06-16).

## v0.5.1 — Configurable update interval and attribute fixes (2026-03-31)

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

- **Allergy risk sensors used stale snapshot data** — `AllergyRiskSensor`
  and `AllergyRiskHourlySensor` read from init-time data instead of
  current `coordinator.data`. After coordinator refresh, these sensors
  still showed the original values. Now reads dynamically from the
  coordinator, matching `PolleninformationSensor` behaviour.

- **Stale risk sensors could not recover** — sensors created with
  `is_stale=True` (empty API response at startup) permanently returned
  `None` even after fresh data arrived. Stale status now only applies
  when the coordinator actually lacks data.

- **README claimed sensors become "unavailable"** — but sensors remain
  available with unknown state when API data is missing. Docs now match
  actual behaviour.

- **Options flow fallback title had extra prefix** — options flow
  generated `"Polleninformation {country} ({lat}, {lon})"` while config
  flow used `"{country} ({lat}, {lon})"`, causing entry title to change
  unexpectedly after reconfigure.

- **Options flow update_interval not sanitized** — corrupted persisted
  value could crash the NumberSelector form. Now cast + clamped before
  rendering, matching the defensive logic in `__init__.py`.

- **API non-JSON response logged as generic error** — if the API
  returned HTML or an empty body, the JSON parse error was caught by the
  generic exception handler and mis-classified as a connection error. Now
  checks content-type before parsing, logs a body preview on failure, and
  raises `PollenApiError` (server issue) instead of
  `PollenApiConnectionError`.

- **Options translations incomplete** — added `options` section with
  proper translations to all 15 non-English language files.

- **Duplicate detection ignored options overrides** — config flow checked
  only `entry.data` for existing coordinates, so after changing location
  via options flow a duplicate entry could be created for the same active
  location. Now uses options-over-data fallback for the comparison.

### New features

- **Configurable update interval** — users can now set the API polling interval
  (1–24 hours, default 8) via the integration options flow. Uses a
  `NumberSelector` with visible value, min/max and unit.

- **Manual refresh via `homeassistant.update_entity`** — documented the
  built-in service for on-demand data refresh in automations and scripts.

### Breaking changes

- **`last_updated` attribute is now a `datetime` object** — previously a
  formatted string (`%Y-%m-%d %H:%M:%S`). HA serializes this to ISO 8601
  with timezone offset, which is more accurate but may require updating
  templates that parsed the old format. Note: the old value was always the
  time of attribute *read*, not the actual last fetch — so any template
  relying on it was already unreliable.

### Internal

- **Test suite** — 84 tests covering API client, coordinator, sensors, utility
  functions and const consistency. Uses `pytest-homeassistant-custom-component`.

- **Defensive interval validation** — persisted `update_interval` is cast,
  clamped to `[1, 24]` and falls back to default on corrupt values.

- **Idempotent unload** — `async_unload_entry` guards against missing keys
  and cleans up empty `hass.data[DOMAIN]`.

- **Config key constants** — sensor setup uses `CONF_*` constants instead of
  raw strings, matching coordinator and config flow.

- **Timezone-aware datetimes throughout** — all remaining `datetime.now()`
  calls in sensor.py replaced with `dt_util.now()` / `dt_util.utcnow()`.

- **Remove hardcoded `DEBUG = True`** — four files had debug flags wrapping
  `_LOGGER.debug()` calls that are already controlled by HA logging config.

- **API key no longer in URL string** — API calls use `params` dict instead
  of string formatting, preventing the key from leaking into stack traces
  or logs. Removed unused `POLLENAT_API_URL` from const.py.

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
