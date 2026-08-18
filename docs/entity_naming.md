# Entity naming

This document describes how the integration decides what an entity is called and
what its ID is. The two are deliberately kept apart: **IDs are English and
stable, names are localized.**

## Identifiers

Every sensor gets a unique ID of the form
`polleninformation_<location_slug>_<allergen_slug>`, and the object ID part of
the entity ID is pinned to the same slug through the `suggested_object_id`
property (`sensor.py`, `PolleninformationSensor.suggested_object_id`, and the
matching properties on `AllergyRiskSensor` and `AllergyRiskHourlySensor`).

For an allergen the slug comes from the allergen's latin name, looked up in
`LATIN_TO_ENGLISH_NAME` (`sensor.py`) and slugified: `Fraxinus` becomes `ash`,
`Poaceae` becomes `grasses`. The map covers all 22 allergens the API returns and
accepts both genus-only and genus-plus-species spellings. When the API sends no
latin name at all, which happens when it puts the genus in the display name
instead (`poll_title` "Artemisia"), the display name is looked up in the same
map. That lookup runs only once the latin lookup and the English language block
have both come up empty, so it cannot outrank them. If a latin name is not
in the map, the code falls back to the English language block and then to the
name the API sent in the configured language. It also logs a warning asking for
a bug report, so a new allergen surfaces instead of quietly producing a
localized ID. The two allergy risk sensors use the fixed slugs `allergy_risk` and
`allergy_risk_hourly`.

## Names

Allergen sensors are named from the API's `poll_title` in the language
configured for the integration, since the API already delivers allergen names
translated. `ALLERGEN_DISPLAY_OVERRIDES` in `const_levels.py` corrects the few
cases where the API sends an English name anyway (ragweed in German and Slovak).
The matching key used to find the allergen's value in the API response is always
the untranslated `poll_title`, so an override never affects the state.

The two allergy risk sensors are named through Home Assistant's translation keys
(`allergy_risk`, `allergy_risk_hourly` in `translations/*.json`), which means
they follow the Home Assistant interface language. When the
"names in integration language" option is enabled in the options flow, an
explicit name from `RISK_SENSOR_NAMES` (`const_levels.py`) is passed instead and
wins over the translation key.

Two override paths therefore already exist: the integration language option in
the options flow, which is global, and Home Assistant's own per-entity rename,
where the registry name wins over whatever the integration supplies.

## Why not plain translation-key naming for allergens

Home Assistant derives an entity ID from the name it sees the first time an
entity is created, and for latin-script languages that name is the translated
one. Relying on translation keys alone therefore produces entity IDs in the
server language. That is exactly what happened by accident in 0.5.2, when the
risk sensors were given translatable names: a German installation ended up with
`sensor.polleninformation_<location>_allergierisiko`, which breaks dashboards
and the pollen forecast card (issue #63).

This is not specific to this integration. Home Assistant core carries recurring
complaints about the same behaviour, for example core issues #130686 ("Entity
IDs got translated (missing documentation)") and #110167 ("Entity-ID's
renamed/translated"). An explicit `suggested_object_id` is the documented escape
hatch: IDs stay English and stable while names stay localized.

There is a second reason. The API already returns allergen names fully
translated, so adding native translation keys for them would mean shipping 22
allergen keys across 16 translation files that duplicate data the API sends on
every fetch.

## History

0.5.2 introduced localized entity IDs by accident. 0.5.3 restored English IDs,
pinned them with `suggested_object_id`, and added automatic migrations for both
the allergen sensors (`migrate_localized_allergen_ids`) and the risk sensors
(`async_migrate_localized_risk_entity_ids`). Both migrations leave an entity ID
the user renamed alone and skip a rename whose target is taken. This document
records the
reasoning so the model is not revisited by accident again.
