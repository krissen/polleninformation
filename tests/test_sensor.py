"""Tests for sensor helper functions and sensor classes."""

import logging
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.polleninformation.const import DOMAIN
from custom_components.polleninformation.sensor import (
    ALLERGEN_ICON_MAP,
    KNOWN_ALLERGEN_SLUGS,
    LATIN_TO_ENGLISH_NAME,
    RISK_SLUGS,
    AllergyRiskHourlySensor,
    AllergyRiskSensor,
    PolleninformationSensor,
    async_setup_entry,
    capitalize_first,
    english_name_for_latin,
    entity_id_available,
    extract_allergen_slug_from_unique_id,
    localized_risk_object_id_suffixes,
    scale_allergy_risk,
)
from custom_components.polleninformation.utils import slugify

# --- Helper function tests (pure, no HA dependency) ---


class TestCapitalizeFirst:
    def test_normal(self):
        assert capitalize_first("birch") == "Birch"

    def test_single_char(self):
        assert capitalize_first("b") == "B"

    def test_empty(self):
        assert capitalize_first("") == ""

    def test_already_capitalized(self):
        assert capitalize_first("Birch") == "Birch"


class TestScaleAllergyRisk:
    def test_zero(self):
        assert scale_allergy_risk(0) == 0

    def test_midpoint(self):
        assert scale_allergy_risk(5.0) == 2

    def test_max(self):
        assert scale_allergy_risk(10) == 4

    def test_quarter(self):
        assert scale_allergy_risk(2.5) == 1

    def test_three_quarter(self):
        assert scale_allergy_risk(7.5) == 3

    def test_none(self):
        assert scale_allergy_risk(None) is None

    def test_string(self):
        assert scale_allergy_risk("abc") is None


class TestExtractAllergenSlug:
    def test_alder(self):
        uid = "polleninformation_hamburg_alder"
        assert extract_allergen_slug_from_unique_id(uid) == "alder"

    def test_allergy_risk(self):
        uid = "polleninformation_hamburg_allergy_risk"
        assert extract_allergen_slug_from_unique_id(uid) == "allergy_risk"

    def test_allergy_risk_hourly(self):
        uid = "polleninformation_hamburg_allergy_risk_hourly"
        assert extract_allergen_slug_from_unique_id(uid) == "allergy_risk_hourly"

    def test_cypress_family(self):
        uid = "polleninformation_hamburg_cypress_family"
        assert extract_allergen_slug_from_unique_id(uid) == "cypress_family"

    def test_invalid_prefix(self):
        assert extract_allergen_slug_from_unique_id("other_hamburg_alder") is None

    def test_unknown_slug(self):
        assert (
            extract_allergen_slug_from_unique_id(
                "polleninformation_hamburg_unknown_thing"
            )
            is None
        )

    def test_empty(self):
        assert extract_allergen_slug_from_unique_id("") is None

    def test_none(self):
        assert extract_allergen_slug_from_unique_id(None) is None


# --- Sensor class tests ---


def _make_coordinator(data, last_updated=None, last_update_success=True):
    """Create a mock coordinator with the given data."""
    coordinator = MagicMock()
    coordinator.data = data
    coordinator.last_updated = last_updated or datetime.now(timezone.utc)
    coordinator.last_update_success = last_update_success
    return coordinator


class TestPolleninformationSensor:
    def _make_sensor(self, coordinator):
        return PolleninformationSensor(
            coordinator=coordinator,
            sensor_type="pollen",
            allergen_name="Erle",
            allergen_en="Alder",
            allergen_slug="alder",
            allergen_latin="Alnus",
            levels_current=["none", "low", "moderate", "high", "very high"],
            levels_en=["none", "low", "moderate", "high", "very high"],
            location_slug="hamburg",
            location_title="Hamburg",
            icon="mdi:tree-outline",
        )

    def test_unique_id(self):
        sensor = self._make_sensor(_make_coordinator(None))
        assert sensor.unique_id == "polleninformation_hamburg_alder"

    def test_native_value(self, mock_api_response):
        sensor = self._make_sensor(_make_coordinator(mock_api_response))
        assert sensor.native_value == "low"

    def test_native_value_no_data(self):
        sensor = self._make_sensor(_make_coordinator(None))
        assert sensor.native_value is None

    def test_attributes_include_forecast(self, mock_api_response):
        sensor = self._make_sensor(_make_coordinator(mock_api_response))
        attrs = sensor.extra_state_attributes
        assert "forecast" in attrs
        assert len(attrs["forecast"]) == 4
        assert attrs["numeric_state"] == 1
        assert attrs["update_success"] is True
        assert attrs["last_updated"] is not None

    def test_attributes_stale(self):
        sensor = PolleninformationSensor(
            coordinator=_make_coordinator(None),
            sensor_type="pollen",
            allergen_name="Erle",
            allergen_en="Alder",
            allergen_slug="alder",
            allergen_latin="Alnus",
            levels_current=["none", "low", "moderate", "high", "very high"],
            levels_en=["none", "low", "moderate", "high", "very high"],
            location_slug="hamburg",
            location_title="Hamburg",
            icon="mdi:tree-outline",
            is_stale=True,
            stale_since="2026-03-25T12:00:00",
        )
        attrs = sensor.extra_state_attributes
        assert attrs["data_stale"] is True
        assert attrs["stale_since"] == "2026-03-25T12:00:00"

    def test_available_when_success(self, mock_api_response):
        sensor = self._make_sensor(
            _make_coordinator(mock_api_response, last_update_success=True)
        )
        assert sensor.available is True

    def test_unavailable_when_failed(self, mock_api_response):
        sensor = self._make_sensor(
            _make_coordinator(mock_api_response, last_update_success=False)
        )
        assert sensor.available is False


class TestAllergyRiskSensor:
    def _make_sensor(self, coordinator):
        return AllergyRiskSensor(
            coordinator=coordinator,
            levels_current=["none", "low", "moderate", "high", "very high"],
            location_slug="hamburg",
            location_title="Hamburg",
        )

    def test_native_value(self, mock_api_response):
        coordinator = _make_coordinator(mock_api_response)
        sensor = self._make_sensor(coordinator)
        # 5.0 / 2.5 = 2.0 -> "moderate"
        assert sensor.native_value == "moderate"

    def test_native_value_stale(self):
        sensor = AllergyRiskSensor(
            coordinator=_make_coordinator(None),
            levels_current=["none", "low", "moderate", "high", "very high"],
            location_slug="hamburg",
            location_title="Hamburg",
            is_stale=True,
        )
        assert sensor.native_value is None

    def test_native_value_recovers_from_stale(self, mock_api_response):
        coordinator = _make_coordinator(mock_api_response)
        sensor = AllergyRiskSensor(
            coordinator=coordinator,
            levels_current=["none", "low", "moderate", "high", "very high"],
            location_slug="hamburg",
            location_title="Hamburg",
            is_stale=True,
        )
        # Even though created as stale, fresh coordinator data is used
        assert sensor.native_value == "moderate"

    def test_attributes_forecast(self, mock_api_response):
        coordinator = _make_coordinator(mock_api_response)
        sensor = self._make_sensor(coordinator)
        attrs = sensor.extra_state_attributes
        assert len(attrs["forecast"]) == 4
        assert attrs["numeric_state"] == 2
        assert attrs["numeric_state_raw"] == 5.0


class TestAllergyRiskHourlySensor:
    def _make_sensor(self, coordinator):
        return AllergyRiskHourlySensor(
            coordinator=coordinator,
            levels_current=["none", "low", "moderate", "high", "very high"],
            location_slug="hamburg",
            location_title="Hamburg",
        )

    def test_unique_id(self, mock_api_response):
        coordinator = _make_coordinator(mock_api_response)
        sensor = self._make_sensor(coordinator)
        assert sensor.unique_id == "polleninformation_hamburg_allergy_risk_hourly"

    def test_attributes_forecast(self, mock_api_response):
        coordinator = _make_coordinator(mock_api_response)
        sensor = self._make_sensor(coordinator)
        attrs = sensor.extra_state_attributes
        assert "forecast" in attrs
        assert len(attrs["forecast"]) > 0

    def test_forecast_times_start_at_local_midnight(self, mock_api_response):
        coordinator = _make_coordinator(mock_api_response)
        sensor = self._make_sensor(coordinator)

        # Non-UTC zone, so a UTC-based implementation would produce a
        # different offset and a different first timestamp.
        fake_now = datetime(2026, 6, 22, 16, 30, tzinfo=ZoneInfo("Europe/Berlin"))

        with patch(
            "custom_components.polleninformation.sensor.dt_util.now",
            return_value=fake_now,
        ):
            forecast = sensor.extra_state_attributes["forecast"]

        # Day 1 starts at local midnight of the current day, not at the
        # current hour: entries before 16:30 are deliberately in the past.
        assert forecast[0]["time"] == "2026-06-22T00:00:00+02:00"
        assert forecast[1]["time"] == "2026-06-22T01:00:00+02:00"
        assert forecast[23]["time"] == "2026-06-22T23:00:00+02:00"
        assert forecast[24]["time"] == "2026-06-23T00:00:00+02:00"


# --- Entity naming: translation keys, display overrides, options toggle ---


class TestRiskSensorTranslationKeys:
    """Risk sensor names come from translation keys, not hardcoded English."""

    def _kwargs(self):
        return {
            "coordinator": _make_coordinator(None),
            "levels_current": ["none", "low", "moderate", "high", "very high"],
            "location_slug": "hamburg",
            "location_title": "Hamburg",
        }

    def test_daily_translation_key(self):
        sensor = AllergyRiskSensor(**self._kwargs())
        assert sensor.translation_key == "allergy_risk"

    def test_hourly_translation_key(self):
        sensor = AllergyRiskHourlySensor(**self._kwargs())
        assert sensor.translation_key == "allergy_risk_hourly"

    def test_daily_name_unset_by_default(self):
        """An unset name is what lets the translation key take effect."""
        sensor = AllergyRiskSensor(**self._kwargs())
        assert getattr(sensor, "_attr_name", None) is None

    def test_hourly_name_unset_by_default(self):
        sensor = AllergyRiskHourlySensor(**self._kwargs())
        assert getattr(sensor, "_attr_name", None) is None

    def test_explicit_name_wins(self):
        sensor = AllergyRiskSensor(name="Allergierisiko", **self._kwargs())
        assert sensor.name == "Allergierisiko"

    def test_explicit_hourly_name_wins(self):
        sensor = AllergyRiskHourlySensor(
            name="Allergierisiko (stündlich)", **self._kwargs()
        )
        assert sensor.name == "Allergierisiko (stündlich)"


class TestDisplayNameSeparateFromMatchKey:
    """A display override must not break the match against poll_title."""

    def _make_sensor(self, coordinator, display_name=None):
        return PolleninformationSensor(
            coordinator=coordinator,
            sensor_type="pollen",
            allergen_name="Ragweed",
            allergen_en="Ragweed",
            allergen_slug="ragweed",
            allergen_latin="Ambrosia artemisiifolia",
            levels_current=["none", "low", "moderate", "high", "very high"],
            levels_en=["none", "low", "moderate", "high", "very high"],
            location_slug="hamburg",
            location_title="Hamburg",
            icon="mdi:flower-pollen",
            display_name=display_name,
        )

    def _coordinator(self):
        return _make_coordinator(
            {
                "contamination": [
                    {
                        "poll_title": "Ragweed (Ambrosia artemisiifolia)",
                        "contamination_1": 3,
                        "contamination_2": 2,
                        "contamination_3": 1,
                        "contamination_4": 0,
                    }
                ]
            }
        )

    def test_name_defaults_to_allergen_name(self):
        assert self._make_sensor(self._coordinator()).name == "Ragweed"

    def test_overridden_name(self):
        sensor = self._make_sensor(self._coordinator(), display_name="Ambrosia")
        assert sensor.name == "Ambrosia"

    def test_state_survives_overridden_name(self):
        """The API still sends "Ragweed", so the value must still resolve."""
        sensor = self._make_sensor(self._coordinator(), display_name="Ambrosia")
        assert sensor.native_value == "high"

    def test_forecast_survives_overridden_name(self):
        sensor = self._make_sensor(self._coordinator(), display_name="Ambrosia")
        attrs = sensor.extra_state_attributes
        assert len(attrs["forecast"]) == 4
        assert attrs["friendly_name"] == "Ambrosia"
        assert attrs["name_en"] == "Ragweed"


RAGWEED_RESPONSE = {
    "contamination": [
        {
            "poll_title": "Ragweed (Ambrosia artemisiifolia)",
            "contamination_1": 3,
            "contamination_2": 2,
            "contamination_3": 1,
            "contamination_4": 0,
        }
    ],
    "allergyrisk": {
        "allergyrisk_1": 5.0,
        "allergyrisk_2": 5.0,
        "allergyrisk_3": 5.0,
        "allergyrisk_4": 5.0,
    },
    "allergyrisk_hourly": {"allergyrisk_hourly_1": [5.0] * 24},
}

RAGWEED_LANGUAGE_BLOCK = {
    "poll_titles": [{"name": "Ragweed", "latin": "Ambrosia artemisiifolia"}]
}


def _make_entry(lang, options=None):
    return MockConfigEntry(
        domain=DOMAIN,
        title="Hamburg",
        data={
            "country": "DE",
            "latitude": 53.5289,
            "longitude": 10.0415,
            "lang": lang,
            "apikey": "test-api-key-12345",
            "location_title": "Hamburg",
            "location_slug": "hamburg",
        },
        options=options or {},
    )


async def _setup_entities(
    hass, lang, options=None, entry=None, response=None, language_block=None
):
    """Run sensor setup for a Ragweed-only response and return the entities."""
    if entry is None:
        entry = _make_entry(lang, options)
        entry.add_to_hass(hass)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = _make_coordinator(
        RAGWEED_RESPONSE if response is None else response
    )

    entities = []

    def _add(new_entities, update_before_add=False):
        entities.extend(new_entities)

    with patch(
        "custom_components.polleninformation.sensor.async_get_language_block",
        AsyncMock(
            return_value=RAGWEED_LANGUAGE_BLOCK
            if language_block is None
            else language_block
        ),
    ):
        await async_setup_entry(hass, entry, _add)
    return entities


def _by_type(entities, cls):
    return next(e for e in entities if isinstance(e, cls))


class TestSetupEntryNaming:
    @pytest.mark.parametrize(
        ("lang", "expected"),
        [("de", "Ambrosia"), ("sk", "Ambrózia"), ("en", "Ragweed")],
    )
    async def test_ragweed_display_name(self, hass, lang, expected):
        entities = await _setup_entities(hass, lang)
        sensor = _by_type(entities, PolleninformationSensor)
        assert sensor.name == expected

    async def test_ragweed_keeps_state_when_renamed(self, hass):
        entities = await _setup_entities(hass, "de")
        sensor = _by_type(entities, PolleninformationSensor)
        assert sensor.name == "Ambrosia"
        assert sensor.native_value is not None

    async def test_risk_names_unset_without_option(self, hass):
        entities = await _setup_entities(hass, "de")
        daily = _by_type(entities, AllergyRiskSensor)
        hourly = _by_type(entities, AllergyRiskHourlySensor)
        assert getattr(daily, "_attr_name", None) is None
        assert getattr(hourly, "_attr_name", None) is None

    async def test_risk_names_set_with_option(self, hass):
        entities = await _setup_entities(
            hass, "de", options={"names_in_integration_language": True}
        )
        assert _by_type(entities, AllergyRiskSensor).name == "Allergierisiko"
        assert (
            _by_type(entities, AllergyRiskHourlySensor).name
            == "Allergierisiko (stündlich)"
        )

    async def test_risk_names_fall_back_to_english(self, hass):
        """An unknown language falls back to the English risk sensor names."""
        entities = await _setup_entities(
            hass, "xx", options={"names_in_integration_language": True}
        )
        assert _by_type(entities, AllergyRiskSensor).name == "Allergy risk"


# --- entity_id stability for the risk sensors (issue #63) ---


DAILY_UNIQUE_ID = "polleninformation_hamburg_allergy_risk"
HOURLY_UNIQUE_ID = "polleninformation_hamburg_allergy_risk_hourly"


class TestRiskSensorSuggestedObjectId:
    """The object_id must stay English regardless of the displayed name."""

    def _kwargs(self):
        return {
            "coordinator": _make_coordinator(None),
            "levels_current": ["none", "low", "moderate", "high", "very high"],
            "location_slug": "hamburg",
            "location_title": "Hamburg",
        }

    def test_daily(self):
        sensor = AllergyRiskSensor(**self._kwargs())
        assert sensor.suggested_object_id == "allergy_risk"

    def test_hourly(self):
        sensor = AllergyRiskHourlySensor(**self._kwargs())
        assert sensor.suggested_object_id == "allergy_risk_hourly"

    def test_daily_with_explicit_name(self):
        sensor = AllergyRiskSensor(name="Allergierisiko", **self._kwargs())
        assert sensor.suggested_object_id == "allergy_risk"

    def test_hourly_with_explicit_name(self):
        sensor = AllergyRiskHourlySensor(
            name="Allergierisiko (stündlich)", **self._kwargs()
        )
        assert sensor.suggested_object_id == "allergy_risk_hourly"

    async def test_setup_entry_keeps_object_id(self, hass):
        """Also with the integration-language option, which sets a name."""
        entities = await _setup_entities(
            hass, "de", options={"names_in_integration_language": True}
        )
        assert _by_type(entities, AllergyRiskSensor).suggested_object_id == (
            "allergy_risk"
        )
        assert _by_type(entities, AllergyRiskHourlySensor).suggested_object_id == (
            "allergy_risk_hourly"
        )


class TestRiskSensorEntityIdCreation:
    """Newly created risk sensors get English entity_ids in a localized HA."""

    @pytest.mark.parametrize("language", ["en", "de"])
    @patch(
        "custom_components.polleninformation.async_get_pollenat_data",
        new_callable=AsyncMock,
    )
    async def test_entity_ids(self, mock_api, hass, language):
        mock_api.return_value = RAGWEED_RESPONSE
        hass.config.language = language
        entry = _make_entry("de")
        entry.add_to_hass(hass)

        with patch(
            "custom_components.polleninformation.sensor.async_get_language_block",
            AsyncMock(return_value=RAGWEED_LANGUAGE_BLOCK),
        ):
            await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()

        ent_reg = er.async_get(hass)
        assert (
            ent_reg.async_get_entity_id("sensor", DOMAIN, DAILY_UNIQUE_ID)
            == "sensor.polleninformation_hamburg_allergy_risk"
        )
        assert (
            ent_reg.async_get_entity_id("sensor", DOMAIN, HOURLY_UNIQUE_ID)
            == "sensor.polleninformation_hamburg_allergy_risk_hourly"
        )


class TestLocalizedRiskObjectIdSuffixes:
    def test_translated_names_are_candidates(self):
        suffixes = localized_risk_object_id_suffixes()
        assert "allergierisiko" in suffixes["allergy_risk"]
        assert "allergirisk" in suffixes["allergy_risk"]
        assert "allergierisiko_stundlich" in suffixes["allergy_risk_hourly"]

    def test_canonical_slug_is_not_a_candidate(self):
        suffixes = localized_risk_object_id_suffixes()
        assert "allergy_risk" not in suffixes["allergy_risk"]
        assert "allergy_risk_hourly" not in suffixes["allergy_risk_hourly"]


class TestMigrateLocalizedRiskEntityIds:
    """Entity_ids created from a translated name are renamed back (issue #63)."""

    def _seed(self, hass, entry, unique_id, object_id):
        ent_reg = er.async_get(hass)
        return ent_reg.async_get_or_create(
            "sensor",
            DOMAIN,
            unique_id,
            suggested_object_id=object_id,
            config_entry=entry,
        ).entity_id

    async def _run(self, hass, seeds, lang="de", options=None):
        entry = _make_entry(lang, options)
        entry.add_to_hass(hass)
        for unique_id, object_id in seeds:
            self._seed(hass, entry, unique_id, object_id)
        await _setup_entities(hass, lang, entry=entry)
        return er.async_get(hass)

    async def test_localized_ids_are_renamed(self, hass):
        ent_reg = await self._run(
            hass,
            [
                (DAILY_UNIQUE_ID, "polleninformation_hamburg_allergierisiko"),
                (
                    HOURLY_UNIQUE_ID,
                    "polleninformation_hamburg_allergierisiko_stundlich",
                ),
            ],
        )
        assert (
            ent_reg.async_get_entity_id("sensor", DOMAIN, DAILY_UNIQUE_ID)
            == "sensor.polleninformation_hamburg_allergy_risk"
        )
        assert (
            ent_reg.async_get_entity_id("sensor", DOMAIN, HOURLY_UNIQUE_ID)
            == "sensor.polleninformation_hamburg_allergy_risk_hourly"
        )

    async def test_swedish_id_is_renamed(self, hass):
        ent_reg = await self._run(
            hass,
            [(DAILY_UNIQUE_ID, "polleninformation_hamburg_allergirisk")],
            lang="sv",
        )
        assert (
            ent_reg.async_get_entity_id("sensor", DOMAIN, DAILY_UNIQUE_ID)
            == "sensor.polleninformation_hamburg_allergy_risk"
        )

    async def test_canonical_id_is_left_alone(self, hass):
        ent_reg = await self._run(
            hass, [(DAILY_UNIQUE_ID, "polleninformation_hamburg_allergy_risk")]
        )
        assert (
            ent_reg.async_get_entity_id("sensor", DOMAIN, DAILY_UNIQUE_ID)
            == "sensor.polleninformation_hamburg_allergy_risk"
        )

    async def test_user_chosen_id_is_left_alone(self, hass):
        """A rename the user made themselves does not match a translation."""
        ent_reg = await self._run(
            hass, [(DAILY_UNIQUE_ID, "pollen_hamburg_my_own_name")]
        )
        assert (
            ent_reg.async_get_entity_id("sensor", DOMAIN, DAILY_UNIQUE_ID)
            == "sensor.pollen_hamburg_my_own_name"
        )

    async def test_pollen_sensor_is_left_alone(self, hass):
        """Only the two risk sensors are in scope."""
        ent_reg = await self._run(
            hass, [("polleninformation_hamburg_ragweed", "polleninformation_ambrosia")]
        )
        assert (
            ent_reg.async_get_entity_id(
                "sensor", DOMAIN, "polleninformation_hamburg_ragweed"
            )
            == "sensor.polleninformation_ambrosia"
        )

    async def test_collision_is_skipped(self, hass):
        """An occupied target entity_id must not raise or steal the id."""
        entry = _make_entry("de")
        entry.add_to_hass(hass)
        ent_reg = er.async_get(hass)
        ent_reg.async_get_or_create(
            "sensor",
            "other_integration",
            "other_unique_id",
            suggested_object_id="polleninformation_hamburg_allergy_risk",
        )
        self._seed(
            hass, entry, DAILY_UNIQUE_ID, "polleninformation_hamburg_allergierisiko"
        )

        await _setup_entities(hass, "de", entry=entry)

        assert (
            ent_reg.async_get_entity_id("sensor", DOMAIN, DAILY_UNIQUE_ID)
            == "sensor.polleninformation_hamburg_allergierisiko"
        )
        assert (
            ent_reg.async_get_entity_id(
                "sensor", "other_integration", "other_unique_id"
            )
            == "sensor.polleninformation_hamburg_allergy_risk"
        )


# --- Allergen slugs come from the latin name, not the localized name ---


# Latin name and English name for every allergen the API returns, sampled from
# the live API for AT, SE, DE and IT with lang=en.
API_LATIN_NAMES = {
    "Ailanthus altissima": "tree of heaven",
    "Alnus": "alder",
    "Alternaria": "fungal spores",
    "Ambrosia": "ragweed",
    "Artemisia": "mugwort",
    "Betula": "birch",
    "Castanea": "sweet chestnut",
    "Corylus": "hazel",
    "Cupressaceae": "cypress family",
    "Fagus": "beech",
    "Fraxinus": "ash",
    "Olea": "olive",
    "Plantago": "plantain",
    "Platanus": "plane tree",
    "Poaceae": "grasses",
    "Quercus": "oak",
    "Rumex": "dock/sorrel",
    "Salix": "willow",
    "Secale": "rye",
    "Tilia": "linden",
    "Ulmus": "elm",
    "Urticaceae": "nettle family",
}

# German response for the allergens that language_map.json does not cover, so
# the pre-fix code fell back to the German name for the slug.
GERMAN_TREE_RESPONSE = {
    "contamination": [
        {
            "poll_title": "Esche (Fraxinus)",
            "contamination_1": 2,
            "contamination_2": 1,
            "contamination_3": 0,
            "contamination_4": 0,
        },
        {
            "poll_title": "Götterbaum (Ailanthus altissima)",
            "contamination_1": 1,
            "contamination_2": 1,
            "contamination_3": 0,
            "contamination_4": 0,
        },
    ],
    "allergyrisk": {"allergyrisk_1": 5.0},
    "allergyrisk_hourly": {"allergyrisk_hourly_1": [5.0] * 24},
}

# language_map.json has no entry for these, which is what the fix works around.
EMPTY_LANGUAGE_BLOCK = {"poll_titles": []}


class TestEnglishNameForLatin:
    def test_exact(self):
        assert english_name_for_latin("Fraxinus") == "ash"

    def test_case_insensitive(self):
        assert english_name_for_latin("fraxinus") == "ash"

    def test_surrounding_whitespace(self):
        assert english_name_for_latin("  Tilia ") == "linden"

    def test_genus_and_species_falls_back_to_genus(self):
        assert english_name_for_latin("Ambrosia artemisiifolia") == "ragweed"

    def test_genus_only_for_a_species_keyed_entry(self):
        assert english_name_for_latin("Ailanthus") == "tree of heaven"

    def test_unknown(self):
        assert english_name_for_latin("Pinus") is None

    def test_empty(self):
        assert english_name_for_latin("") is None

    def test_whitespace_only(self):
        assert english_name_for_latin("   ") is None

    def test_none(self):
        assert english_name_for_latin(None) is None


class TestLatinMapCoverage:
    def test_every_api_latin_name_is_mapped(self):
        assert LATIN_TO_ENGLISH_NAME == API_LATIN_NAMES

    @pytest.mark.parametrize(("latin", "name"), sorted(API_LATIN_NAMES.items()))
    def test_every_allergen_has_an_icon(self, latin, name):
        """A missing icon silently degrades to the generic pollen icon."""
        assert slugify(name) in ALLERGEN_ICON_MAP

    def test_slugs_are_distinct(self):
        slugs = [slugify(name) for name in LATIN_TO_ENGLISH_NAME.values()]
        assert len(slugs) == len(set(slugs))


class TestAllergenSlugFromLatin:
    async def test_slug_is_english_for_german_response(self, hass):
        entities = await _setup_entities(
            hass,
            "de",
            response=GERMAN_TREE_RESPONSE,
            language_block=EMPTY_LANGUAGE_BLOCK,
        )
        unique_ids = {e.unique_id for e in entities}
        assert "polleninformation_hamburg_ash" in unique_ids
        assert "polleninformation_hamburg_tree_of_heaven" in unique_ids

    async def test_display_name_stays_localized(self, hass):
        entities = await _setup_entities(
            hass,
            "de",
            response=GERMAN_TREE_RESPONSE,
            language_block=EMPTY_LANGUAGE_BLOCK,
        )
        names = {e.name for e in entities if isinstance(e, PolleninformationSensor)}
        assert "Esche" in names

    async def test_english_name_attribute_and_icon(self, hass):
        entities = await _setup_entities(
            hass,
            "de",
            response=GERMAN_TREE_RESPONSE,
            language_block=EMPTY_LANGUAGE_BLOCK,
        )
        ash = next(
            e for e in entities if e.unique_id == "polleninformation_hamburg_ash"
        )
        assert ash.extra_state_attributes["name_en"] == "ash"
        assert ash.extra_state_attributes["allergen_slug"] == "ash"
        assert ash.icon == "mdi:tree"

    async def test_state_still_resolves(self, hass):
        """The value lookup matches on the name the API sent, not the slug."""
        entities = await _setup_entities(
            hass,
            "de",
            response=GERMAN_TREE_RESPONSE,
            language_block=EMPTY_LANGUAGE_BLOCK,
        )
        ash = next(
            e for e in entities if e.unique_id == "polleninformation_hamburg_ash"
        )
        # German levels, because the entry is configured for German.
        assert ash.native_value == "mäßig"


class TestMigrateLocalizedAllergenIds:
    """Localized allergen unique_ids and entity_ids are renamed (issue #63)."""

    def _seed(self, hass, entry, unique_id, object_id):
        return er.async_get(hass).async_get_or_create(
            "sensor",
            DOMAIN,
            unique_id,
            suggested_object_id=object_id,
            config_entry=entry,
        )

    async def _run(self, hass, seeds):
        entry = _make_entry("de")
        entry.add_to_hass(hass)
        for unique_id, object_id in seeds:
            self._seed(hass, entry, unique_id, object_id)
        await _setup_entities(
            hass,
            "de",
            entry=entry,
            response=GERMAN_TREE_RESPONSE,
            language_block=EMPTY_LANGUAGE_BLOCK,
        )
        return er.async_get(hass)

    async def test_unique_id_and_entity_id_are_renamed(self, hass):
        ent_reg = await self._run(
            hass,
            [
                ("polleninformation_hamburg_esche", "polleninformation_hamburg_esche"),
                (
                    "polleninformation_hamburg_gotterbaum",
                    "polleninformation_hamburg_gotterbaum",
                ),
            ],
        )
        assert (
            ent_reg.async_get_entity_id(
                "sensor", DOMAIN, "polleninformation_hamburg_ash"
            )
            == "sensor.polleninformation_hamburg_ash"
        )
        assert (
            ent_reg.async_get_entity_id(
                "sensor", DOMAIN, "polleninformation_hamburg_tree_of_heaven"
            )
            == "sensor.polleninformation_hamburg_tree_of_heaven"
        )
        assert (
            ent_reg.async_get_entity_id(
                "sensor", DOMAIN, "polleninformation_hamburg_esche"
            )
            is None
        )

    async def test_user_renamed_entity_id_is_kept(self, hass):
        """The unique_id is still fixed, but a chosen entity_id is not touched."""
        ent_reg = await self._run(
            hass, [("polleninformation_hamburg_esche", "pollen_ash_tree")]
        )
        assert (
            ent_reg.async_get_entity_id(
                "sensor", DOMAIN, "polleninformation_hamburg_ash"
            )
            == "sensor.pollen_ash_tree"
        )

    async def test_canonical_id_is_untouched(self, hass):
        """An English installation already has the canonical ids."""
        ent_reg = await self._run(
            hass, [("polleninformation_hamburg_ash", "polleninformation_hamburg_ash")]
        )
        assert (
            ent_reg.async_get_entity_id(
                "sensor", DOMAIN, "polleninformation_hamburg_ash"
            )
            == "sensor.polleninformation_hamburg_ash"
        )

    async def test_unrelated_entity_is_untouched(self, hass):
        ent_reg = await self._run(
            hass, [("polleninformation_hamburg_birch", "polleninformation_birke")]
        )
        assert (
            ent_reg.async_get_entity_id(
                "sensor", DOMAIN, "polleninformation_hamburg_birch"
            )
            == "sensor.polleninformation_birke"
        )

    async def test_taken_unique_id_is_skipped(self, hass):
        ent_reg = await self._run(
            hass,
            [
                ("polleninformation_hamburg_esche", "polleninformation_hamburg_esche"),
                ("polleninformation_hamburg_ash", "polleninformation_hamburg_ash"),
            ],
        )
        assert (
            ent_reg.async_get_entity_id(
                "sensor", DOMAIN, "polleninformation_hamburg_esche"
            )
            == "sensor.polleninformation_hamburg_esche"
        )
        assert (
            ent_reg.async_get_entity_id(
                "sensor", DOMAIN, "polleninformation_hamburg_ash"
            )
            == "sensor.polleninformation_hamburg_ash"
        )

    async def test_taken_entity_id_keeps_entity_id_but_fixes_unique_id(self, hass):
        entry = _make_entry("de")
        entry.add_to_hass(hass)
        ent_reg = er.async_get(hass)
        ent_reg.async_get_or_create(
            "sensor",
            "other_integration",
            "other_unique_id",
            suggested_object_id="polleninformation_hamburg_ash",
        )
        self._seed(
            hass,
            entry,
            "polleninformation_hamburg_esche",
            "polleninformation_hamburg_esche",
        )

        await _setup_entities(
            hass,
            "de",
            entry=entry,
            response=GERMAN_TREE_RESPONSE,
            language_block=EMPTY_LANGUAGE_BLOCK,
        )

        assert (
            ent_reg.async_get_entity_id(
                "sensor", DOMAIN, "polleninformation_hamburg_ash"
            )
            == "sensor.polleninformation_hamburg_esche"
        )
        assert (
            ent_reg.async_get_entity_id(
                "sensor", "other_integration", "other_unique_id"
            )
            == "sensor.polleninformation_hamburg_ash"
        )


UNKNOWN_ALLERGEN_RESPONSE = {
    "contamination": [
        {
            "poll_title": "Kiefer (Pinus)",
            "contamination_1": 1,
            "contamination_2": 0,
            "contamination_3": 0,
            "contamination_4": 0,
        }
    ],
    "allergyrisk": {"allergyrisk_1": 5.0},
    "allergyrisk_hourly": {"allergyrisk_hourly_1": [5.0] * 24},
}


class TestUnknownAllergenFallback:
    """An allergen no map knows about still gets a sensor, plus a warning."""

    async def _setup(self, hass):
        return await _setup_entities(
            hass,
            "de",
            response=UNKNOWN_ALLERGEN_RESPONSE,
            language_block=EMPTY_LANGUAGE_BLOCK,
        )

    async def test_falls_back_to_the_localized_name(self, hass):
        entities = await self._setup(hass)
        unique_ids = {e.unique_id for e in entities}
        assert "polleninformation_hamburg_kiefer" in unique_ids

    async def test_warns_once_with_the_latin_name(self, hass, caplog):
        await self._setup(hass)
        warnings = [
            r.getMessage()
            for r in caplog.records
            if r.levelname == "WARNING" and "Unknown allergen" in r.getMessage()
        ]
        assert len(warnings) == 1
        assert "Kiefer" in warnings[0]
        assert "Pinus" in warnings[0]

    async def test_no_warning_for_a_mapped_allergen(self, hass, caplog):
        await _setup_entities(
            hass,
            "de",
            response=GERMAN_TREE_RESPONSE,
            language_block=EMPTY_LANGUAGE_BLOCK,
        )
        assert not [r for r in caplog.records if "Unknown allergen" in r.getMessage()]

    async def test_no_migration_for_an_unknown_allergen(self, hass):
        """Nothing to rename: the fallback slug is the only one we ever had."""
        entry = _make_entry("de")
        entry.add_to_hass(hass)
        ent_reg = er.async_get(hass)
        ent_reg.async_get_or_create(
            "sensor",
            DOMAIN,
            "polleninformation_hamburg_kiefer",
            suggested_object_id="polleninformation_hamburg_kiefer",
            config_entry=entry,
        )
        await _setup_entities(
            hass,
            "de",
            entry=entry,
            response=UNKNOWN_ALLERGEN_RESPONSE,
            language_block=EMPTY_LANGUAGE_BLOCK,
        )
        assert (
            ent_reg.async_get_entity_id(
                "sensor", DOMAIN, "polleninformation_hamburg_kiefer"
            )
            == "sensor.polleninformation_hamburg_kiefer"
        )


# The API sometimes sends the latin genus as the display name and leaves the
# latin field empty, e.g. "Artemisia" with no "(...)" in poll_title and no
# matching entry in the language block. The name is nonetheless a known key in
# LATIN_TO_ENGLISH_NAME.
LATIN_GENUS_AS_NAME_RESPONSE = {
    "contamination": [
        {
            "poll_title": "Artemisia",
            "contamination_1": 1,
            "contamination_2": 0,
            "contamination_3": 0,
            "contamination_4": 0,
        }
    ],
    "allergyrisk": {"allergyrisk_1": 5.0},
    "allergyrisk_hourly": {"allergyrisk_hourly_1": [5.0] * 24},
}


class TestLatinGenusAsDisplayName:
    """A latin genus arriving as the display name still resolves through the map.

    Regression test for issue #71: "Artemisia" arrived as the poll_title with
    an empty latin field, so the latin-keyed lookup missed it. The sensor was
    slugged "artemisia" with the default icon and a spurious "Unknown allergen"
    warning fired on every refresh -- even though "Artemisia" is a known key in
    LATIN_TO_ENGLISH_NAME that resolves to "mugwort".
    """

    async def _setup(self, hass):
        return await _setup_entities(
            hass,
            "de",
            response=LATIN_GENUS_AS_NAME_RESPONSE,
            language_block=EMPTY_LANGUAGE_BLOCK,
        )

    async def test_resolves_to_the_canonical_english_slug(self, hass):
        entities = await self._setup(hass)
        unique_ids = {e.unique_id for e in entities if e.unique_id}
        assert "polleninformation_hamburg_mugwort" in unique_ids
        assert "polleninformation_hamburg_artemisia" not in unique_ids

    async def test_uses_the_mapped_icon(self, hass):
        entities = await self._setup(hass)
        sensor = next(
            e
            for e in entities
            if isinstance(e, PolleninformationSensor)
            and e.unique_id == "polleninformation_hamburg_mugwort"
        )
        assert sensor.icon == ALLERGEN_ICON_MAP["mugwort"]

    async def test_no_unknown_allergen_warning(self, hass, caplog):
        with caplog.at_level(logging.WARNING):
            await self._setup(hass)
        assert not [r for r in caplog.records if "Unknown allergen" in r.getMessage()]

    async def test_reports_the_genus_as_the_latin_name(self, hass):
        """The display name is a proven latin genus, so it is the latin name.

        The API left the latin field empty, but the map lookup that resolved
        the slug proved the display name is a latin genus. Reporting an empty
        name_la for exactly the allergens this resolves would waste that.
        """
        entities = await self._setup(hass)
        sensor = next(
            e
            for e in entities
            if isinstance(e, PolleninformationSensor)
            and e.unique_id == "polleninformation_hamburg_mugwort"
        )
        assert sensor.extra_state_attributes["name_la"] == "Artemisia"

    async def test_existing_buggy_slug_entity_is_migrated(self, hass):
        """An entity from the pre-fix "artemisia" slug is carried to "mugwort".

        Before the fix this allergen was slugged "artemisia", so an upgrading
        user already has that entity in the registry. The fix must rename it to
        the canonical "mugwort" -- via the same migration path used for
        localized slugs -- so history and automations survive instead of the
        old sensor being orphaned beside a new one.
        """
        entry = _make_entry("de")
        entry.add_to_hass(hass)
        ent_reg = er.async_get(hass)
        ent_reg.async_get_or_create(
            "sensor",
            DOMAIN,
            "polleninformation_hamburg_artemisia",
            suggested_object_id="polleninformation_hamburg_artemisia",
            config_entry=entry,
        )
        await _setup_entities(
            hass,
            "de",
            entry=entry,
            response=LATIN_GENUS_AS_NAME_RESPONSE,
            language_block=EMPTY_LANGUAGE_BLOCK,
        )
        assert (
            ent_reg.async_get_entity_id(
                "sensor", DOMAIN, "polleninformation_hamburg_mugwort"
            )
            == "sensor.polleninformation_hamburg_mugwort"
        )
        assert (
            ent_reg.async_get_entity_id(
                "sensor", DOMAIN, "polleninformation_hamburg_artemisia"
            )
            is None
        )


# An allergen whose latin name the static map does not know, but whose display
# name happens to be the latin genus of a different allergen. The English
# language block knows the latin name, so it must win: the display name is only
# a last resort.
UNKNOWN_LATIN_WITH_GENUS_NAME_RESPONSE = {
    "contamination": [
        {
            "poll_title": "Artemisia (Asteraceae)",
            "contamination_1": 1,
            "contamination_2": 0,
            "contamination_3": 0,
            "contamination_4": 0,
        }
    ],
    "allergyrisk": {"allergyrisk_1": 5.0},
    "allergyrisk_hourly": {"allergyrisk_hourly_1": [5.0] * 24},
}

COMPOSITE_FAMILY_LANGUAGE_BLOCK = {
    "poll_titles": [{"name": "Composite family", "latin": "Asteraceae"}]
}


class TestEnglishBlockOutranksTheDisplayName:
    """The English language block wins over a display name that is a genus.

    The display-name lookup exists for allergens whose latin name is missing.
    It must not outrank the English language block, because slugging the
    allergen from the wrong source both names the entity after a different
    allergen and makes the migration rename an existing entity onto it.
    """

    async def _setup(self, hass, entry=None):
        return await _setup_entities(
            hass,
            "de",
            entry=entry,
            response=UNKNOWN_LATIN_WITH_GENUS_NAME_RESPONSE,
            language_block=COMPOSITE_FAMILY_LANGUAGE_BLOCK,
        )

    async def test_slug_comes_from_the_english_block(self, hass):
        entities = await self._setup(hass)
        unique_ids = {e.unique_id for e in entities if e.unique_id}
        assert "polleninformation_hamburg_composite_family" in unique_ids
        assert "polleninformation_hamburg_mugwort" not in unique_ids

    async def test_no_rename_onto_another_allergen(self, hass):
        entry = _make_entry("de")
        entry.add_to_hass(hass)
        ent_reg = er.async_get(hass)
        ent_reg.async_get_or_create(
            "sensor",
            DOMAIN,
            "polleninformation_hamburg_composite_family",
            suggested_object_id="polleninformation_hamburg_composite_family",
            config_entry=entry,
        )

        await self._setup(hass, entry=entry)

        assert (
            ent_reg.async_get_entity_id(
                "sensor", DOMAIN, "polleninformation_hamburg_composite_family"
            )
            == "sensor.polleninformation_hamburg_composite_family"
        )
        assert (
            ent_reg.async_get_entity_id(
                "sensor", DOMAIN, "polleninformation_hamburg_mugwort"
            )
            is None
        )


class TestPresentLatinIsAuthoritative:
    """A latin name the API sent wins even when nothing can resolve it.

    The same response as above, but no language block knows the latin name
    either. The display name must still not be read as a latin genus: the API
    said this allergen is Asteraceae, so resolving it to mugwort would name the
    entity after a different allergen and migrate an existing one onto it.
    """

    async def _setup(self, hass, entry=None):
        return await _setup_entities(
            hass,
            "de",
            entry=entry,
            response=UNKNOWN_LATIN_WITH_GENUS_NAME_RESPONSE,
            language_block=EMPTY_LANGUAGE_BLOCK,
        )

    async def test_falls_back_to_the_configured_language_name(self, hass):
        entities = await self._setup(hass)
        unique_ids = {e.unique_id for e in entities if e.unique_id}
        assert "polleninformation_hamburg_artemisia" in unique_ids
        assert "polleninformation_hamburg_mugwort" not in unique_ids

    async def test_keeps_the_latin_name_the_api_sent(self, hass):
        entities = await self._setup(hass)
        sensor = next(
            e
            for e in entities
            if isinstance(e, PolleninformationSensor)
            and e.unique_id == "polleninformation_hamburg_artemisia"
        )
        assert sensor.extra_state_attributes["name_la"] == "Asteraceae"

    async def test_warns_about_the_unknown_allergen(self, hass, caplog):
        with caplog.at_level(logging.WARNING):
            await self._setup(hass)
        assert [r for r in caplog.records if "Unknown allergen" in r.getMessage()]

    async def test_no_rename_is_queued(self, hass):
        entry = _make_entry("de")
        entry.add_to_hass(hass)
        ent_reg = er.async_get(hass)
        ent_reg.async_get_or_create(
            "sensor",
            DOMAIN,
            "polleninformation_hamburg_artemisia",
            suggested_object_id="polleninformation_hamburg_artemisia",
            config_entry=entry,
        )

        await self._setup(hass, entry=entry)

        assert (
            ent_reg.async_get_entity_id(
                "sensor", DOMAIN, "polleninformation_hamburg_artemisia"
            )
            == "sensor.polleninformation_hamburg_artemisia"
        )
        assert (
            ent_reg.async_get_entity_id(
                "sensor", DOMAIN, "polleninformation_hamburg_mugwort"
            )
            is None
        )


# The canonical slug for every allergen, pinned. These slugs are a public
# contract: they are the entity_id suffix, they are in every unique_id, and
# the pollen forecast card matches on them. A change to an API display name or
# to slugify() must fail here rather than silently rename entities.
CANONICAL_ALLERGEN_SLUGS = {
    "Ailanthus altissima": "tree_of_heaven",
    "Alnus": "alder",
    "Alternaria": "fungal_spores",
    "Ambrosia": "ragweed",
    "Artemisia": "mugwort",
    "Betula": "birch",
    "Castanea": "sweet_chestnut",
    "Corylus": "hazel",
    "Cupressaceae": "cypress_family",
    "Fagus": "beech",
    "Fraxinus": "ash",
    "Olea": "olive",
    "Plantago": "plantain",
    "Platanus": "plane_tree",
    "Poaceae": "grasses",
    "Quercus": "oak",
    "Rumex": "dock_sorrel",
    "Salix": "willow",
    "Secale": "rye",
    "Tilia": "linden",
    "Ulmus": "elm",
    "Urticaceae": "nettle_family",
}

EXPECTED_KNOWN_SLUGS = frozenset(CANONICAL_ALLERGEN_SLUGS.values()) | {
    "allergy_risk",
    "allergy_risk_hourly",
}


class TestCanonicalSlugSet:
    """Pins the slug set so a rename cannot happen unnoticed."""

    def test_known_allergen_slugs(self):
        assert KNOWN_ALLERGEN_SLUGS == EXPECTED_KNOWN_SLUGS

    def test_slugs_from_the_latin_map(self):
        """A set comparison, so two allergens collapsing onto one slug fails."""
        assert {slugify(name) for name in LATIN_TO_ENGLISH_NAME.values()} == set(
            CANONICAL_ALLERGEN_SLUGS.values()
        )

    @pytest.mark.parametrize(
        ("latin", "slug"), sorted(CANONICAL_ALLERGEN_SLUGS.items())
    )
    def test_slug_per_latin_name(self, latin, slug):
        assert slugify(english_name_for_latin(latin)) == slug

    def test_icon_map_covers_exactly_the_canonical_slugs(self):
        """An icon for a slug that cannot occur is as wrong as a missing one."""
        assert set(ALLERGEN_ICON_MAP) - {"default"} == set(
            CANONICAL_ALLERGEN_SLUGS.values()
        )

    def test_risk_slugs(self):
        assert set(RISK_SLUGS) == {"allergy_risk", "allergy_risk_hourly"}


class TestTranslationFileReadFailure:
    """A broken translation file must not hide why it was skipped."""

    def test_debug_log_carries_the_exception(self, caplog):
        localized_risk_object_id_suffixes.cache_clear()
        try:
            with (
                caplog.at_level(logging.DEBUG),
                patch(
                    "custom_components.polleninformation.sensor.Path.read_text",
                    side_effect=OSError("boom"),
                ),
            ):
                localized_risk_object_id_suffixes()
            records = [
                r
                for r in caplog.records
                if "Could not read translation file" in r.getMessage()
            ]
            assert records
            assert all(r.exc_info for r in records)
        finally:
            localized_risk_object_id_suffixes.cache_clear()

    def test_names_survive_from_the_static_map(self):
        """RISK_SENSOR_NAMES still supplies candidates without the files."""
        localized_risk_object_id_suffixes.cache_clear()
        try:
            with patch(
                "custom_components.polleninformation.sensor.Path.read_text",
                side_effect=OSError("boom"),
            ):
                suffixes = localized_risk_object_id_suffixes()
            assert "allergierisiko" in suffixes["allergy_risk"]
        finally:
            localized_risk_object_id_suffixes.cache_clear()


class TestOnlyGeneratedEntityIdsAreRenamed:
    """A suffix match is not enough: the entity_id must be the generated one.

    A user-chosen entity_id can end in the old slug without this integration
    ever having produced it, and renaming it would be a rename the user did
    not ask for.
    """

    def _seed(self, hass, entry, unique_id, object_id):
        return er.async_get(hass).async_get_or_create(
            "sensor",
            DOMAIN,
            unique_id,
            suggested_object_id=object_id,
            config_entry=entry,
        )

    async def test_allergen_entity_id_with_a_different_prefix_is_kept(self, hass):
        entry = _make_entry("de")
        entry.add_to_hass(hass)
        # Ends with "_esche", but the prefix is not ours.
        self._seed(
            hass, entry, "polleninformation_hamburg_esche", "pollen_hamburg_esche"
        )

        await _setup_entities(
            hass,
            "de",
            entry=entry,
            response=GERMAN_TREE_RESPONSE,
            language_block=EMPTY_LANGUAGE_BLOCK,
        )

        ent_reg = er.async_get(hass)
        # The unique_id is still corrected; only the entity_id is left alone.
        assert (
            ent_reg.async_get_entity_id(
                "sensor", DOMAIN, "polleninformation_hamburg_ash"
            )
            == "sensor.pollen_hamburg_esche"
        )

    async def test_allergen_entity_id_for_another_location_is_kept(self, hass):
        entry = _make_entry("de")
        entry.add_to_hass(hass)
        self._seed(
            hass,
            entry,
            "polleninformation_hamburg_esche",
            "polleninformation_bremen_esche",
        )

        await _setup_entities(
            hass,
            "de",
            entry=entry,
            response=GERMAN_TREE_RESPONSE,
            language_block=EMPTY_LANGUAGE_BLOCK,
        )

        ent_reg = er.async_get(hass)
        assert (
            ent_reg.async_get_entity_id(
                "sensor", DOMAIN, "polleninformation_hamburg_ash"
            )
            == "sensor.polleninformation_bremen_esche"
        )

    async def test_risk_entity_id_with_a_different_prefix_is_kept(self, hass):
        entry = _make_entry("de")
        entry.add_to_hass(hass)
        # Ends with the German translation, but we never generated it.
        self._seed(hass, entry, DAILY_UNIQUE_ID, "my_own_allergierisiko")

        await _setup_entities(hass, "de", entry=entry)

        ent_reg = er.async_get(hass)
        assert (
            ent_reg.async_get_entity_id("sensor", DOMAIN, DAILY_UNIQUE_ID)
            == "sensor.my_own_allergierisiko"
        )

    async def test_generated_risk_entity_id_is_still_renamed(self, hass):
        """The strictness must not stop the migration it exists for."""
        entry = _make_entry("de")
        entry.add_to_hass(hass)
        self._seed(
            hass, entry, DAILY_UNIQUE_ID, "polleninformation_hamburg_allergierisiko"
        )

        await _setup_entities(hass, "de", entry=entry)

        ent_reg = er.async_get(hass)
        assert (
            ent_reg.async_get_entity_id("sensor", DOMAIN, DAILY_UNIQUE_ID)
            == "sensor.polleninformation_hamburg_allergy_risk"
        )


class TestStateMachineCollision:
    """A YAML or template entity holds an entity_id without a registry entry.

    The registry refuses to move an entity_id onto one that is occupied in the
    state machine, so a registry-only check let async_update_entity raise and
    abort setup.
    """

    def _seed(self, hass, entry, unique_id, object_id):
        return er.async_get(hass).async_get_or_create(
            "sensor",
            DOMAIN,
            unique_id,
            suggested_object_id=object_id,
            config_entry=entry,
        )

    def test_availability_sees_the_state_machine(self, hass):
        ent_reg = er.async_get(hass)
        hass.states.async_set("sensor.polleninformation_hamburg_ash", "low")
        assert not entity_id_available(
            hass, ent_reg, "sensor.polleninformation_hamburg_ash"
        )
        assert entity_id_available(
            hass, ent_reg, "sensor.polleninformation_hamburg_birch"
        )

    async def test_allergen_setup_survives_a_state_only_collision(self, hass):
        entry = _make_entry("de")
        entry.add_to_hass(hass)
        self._seed(
            hass,
            entry,
            "polleninformation_hamburg_esche",
            "polleninformation_hamburg_esche",
        )
        hass.states.async_set("sensor.polleninformation_hamburg_ash", "low")

        # Must not raise.
        await _setup_entities(
            hass,
            "de",
            entry=entry,
            response=GERMAN_TREE_RESPONSE,
            language_block=EMPTY_LANGUAGE_BLOCK,
        )

        ent_reg = er.async_get(hass)
        # unique_id corrected, entity_id kept because the target is occupied.
        assert (
            ent_reg.async_get_entity_id(
                "sensor", DOMAIN, "polleninformation_hamburg_ash"
            )
            == "sensor.polleninformation_hamburg_esche"
        )

    async def test_risk_setup_survives_a_state_only_collision(self, hass):
        entry = _make_entry("de")
        entry.add_to_hass(hass)
        self._seed(
            hass, entry, DAILY_UNIQUE_ID, "polleninformation_hamburg_allergierisiko"
        )
        hass.states.async_set("sensor.polleninformation_hamburg_allergy_risk", "low")

        # Must not raise.
        await _setup_entities(hass, "de", entry=entry)

        ent_reg = er.async_get(hass)
        assert (
            ent_reg.async_get_entity_id("sensor", DOMAIN, DAILY_UNIQUE_ID)
            == "sensor.polleninformation_hamburg_allergierisiko"
        )


# --- Stale sensors recreated from the registry (issue #73) ---


EMPTY_RESPONSE = {"contamination": [], "allergyrisk": {}, "allergyrisk_hourly": {}}

GERMAN_BIRCH_RESPONSE = {
    "contamination": [
        {
            "poll_title": "Birke (Betula)",
            "contamination_1": 3,
            "contamination_2": 2,
            "contamination_3": 1,
            "contamination_4": 0,
        }
    ],
    "allergyrisk": {},
    "allergyrisk_hourly": {},
}

ENGLISH_DOCK_SORREL_RESPONSE = {
    "contamination": [
        {
            "poll_title": "Dock/Sorrel (Rumex)",
            "contamination_1": 2,
            "contamination_2": 2,
            "contamination_3": 1,
            "contamination_4": 0,
        }
    ],
    "allergyrisk": {},
    "allergyrisk_hourly": {},
}


GENUS_PREFIXED_NAME_RESPONSE = {
    "contamination": [
        {
            "poll_title": "Ambrosia hojas",
            "contamination_1": 2,
            "contamination_2": 2,
            "contamination_3": 1,
            "contamination_4": 0,
        }
    ],
    "allergyrisk": {},
    "allergyrisk_hourly": {},
}


BINOMIAL_NAME_RESPONSE = {
    "contamination": [
        {
            "poll_title": "Ailanthus altissima",
            "contamination_1": 2,
            "contamination_2": 1,
            "contamination_3": 0,
            "contamination_4": 0,
        }
    ],
    "allergyrisk": {},
    "allergyrisk_hourly": {},
}


async def _recreate_stale(hass, lang, unique_id, language_block=None):
    """Run setup against an empty response so a registry entity is recreated."""
    entry = _make_entry(lang)
    entry.add_to_hass(hass)
    ent_reg = er.async_get(hass)
    ent_reg.async_get_or_create(
        "sensor",
        DOMAIN,
        unique_id,
        suggested_object_id=unique_id,
        config_entry=entry,
    )
    entities = await _setup_entities(
        hass,
        lang,
        entry=entry,
        response=EMPTY_RESPONSE,
        language_block=language_block or EMPTY_LANGUAGE_BLOCK,
    )
    return _by_type(entities, PolleninformationSensor)


class TestStaleSensorRecovery:
    """A sensor recreated during an empty response must recover on any language."""

    async def test_german_sensor_recovers_on_localized_poll_title(self, hass):
        sensor = await _recreate_stale(hass, "de", "polleninformation_hamburg_birch")
        sensor.coordinator.data = GERMAN_BIRCH_RESPONSE
        assert sensor.native_value == "hoch"

    async def test_german_forecast_recovers(self, hass):
        sensor = await _recreate_stale(hass, "de", "polleninformation_hamburg_birch")
        sensor.coordinator.data = GERMAN_BIRCH_RESPONSE
        forecast = sensor.extra_state_attributes["forecast"]
        assert [day["level"] for day in forecast] == [3, 2, 1, 0]

    async def test_english_dock_sorrel_recovers(self, hass):
        sensor = await _recreate_stale(
            hass, "en", "polleninformation_hamburg_dock_sorrel"
        )
        sensor.coordinator.data = ENGLISH_DOCK_SORREL_RESPONSE
        assert sensor.native_value == "moderate"

    async def test_latin_name_is_derived_from_the_slug(self, hass):
        sensor = await _recreate_stale(hass, "de", "polleninformation_hamburg_birch")
        sensor.coordinator.data = GERMAN_BIRCH_RESPONSE
        assert sensor.extra_state_attributes["name_la"] == "Betula"

    async def test_recovers_when_the_latin_genus_is_the_display_name(self, hass):
        """Issue #71 arrives without parentheses, so there is no latin to read.

        A stale mugwort sensor on a Spanish install sees "Artemisia" as the
        whole poll_title; its own name is "Mugwort", so only the map lookup on
        the display name itself can identify the entry.
        """
        sensor = await _recreate_stale(hass, "es", "polleninformation_hamburg_mugwort")
        sensor.coordinator.data = LATIN_GENUS_AS_NAME_RESPONSE
        assert sensor.native_value == "bajo"

    async def test_stale_flag_clears_once_the_allergen_is_found(self, hass):
        """A recovered sensor must stop claiming its data is stale.

        The flag is set in the constructor and async_setup_entry does not run
        again when the API recovers, so it has to be derived from whether the
        allergen was actually found.
        """
        sensor = await _recreate_stale(hass, "de", "polleninformation_hamburg_birch")
        sensor.coordinator.data = GERMAN_BIRCH_RESPONSE
        attrs = sensor.extra_state_attributes
        assert "data_stale" not in attrs
        assert "stale_since" not in attrs

    async def test_stale_flag_stays_while_the_allergen_is_missing(self, hass):
        """Data for other allergens only is still no data for this one."""
        sensor = await _recreate_stale(hass, "de", "polleninformation_hamburg_birch")
        sensor.coordinator.data = LATIN_GENUS_AS_NAME_RESPONSE
        attrs = sensor.extra_state_attributes
        assert attrs["data_stale"] is True
        assert attrs["stale_since"] is not None

    async def test_recovers_when_the_display_name_is_a_binomial_key(self, hass):
        """A binomial key in the latin map: "Ailanthus altissima".

        Counting words would reject it, but it is a latin name the map knows,
        so a stale tree of heaven sensor must pick it up like any other.
        """
        sensor = await _recreate_stale(
            hass, "de", "polleninformation_hamburg_tree_of_heaven"
        )
        sensor.coordinator.data = BINOMIAL_NAME_RESPONSE
        assert sensor.native_value == "mäßig"

    async def test_a_two_word_name_starting_with_a_genus_does_not_match(self, hass):
        """The display-name lookup holds only for a name that IS the genus.

        "Ambrosia hojas" is prose that happens to start with a latin genus, so
        matching it to the ragweed sensor would be a guess, not an
        identification.
        """
        sensor = await _recreate_stale(hass, "es", "polleninformation_hamburg_ragweed")
        sensor.coordinator.data = GENUS_PREFIXED_NAME_RESPONSE
        assert sensor.native_value is None


T1 = datetime(2026, 8, 18, 6, 0, tzinfo=timezone.utc)
T2 = datetime(2026, 8, 18, 18, 0, tzinfo=timezone.utc)


def _frozen(moment):
    """Patch the sensor module's clock to a fixed moment."""
    return patch(
        "custom_components.polleninformation.sensor.dt_util.now",
        return_value=moment,
    )


class TestStaleSinceFollowsTheCurrentOutage:
    """stale_since must date the outage being reported, not the first one.

    The timestamp is a constructor value, and setup does not run again when
    the API recovers, so a second outage would otherwise republish the first
    outage's timestamp and appear to have lasted for the whole gap.
    """

    async def _recreated_at(self, hass, moment):
        entry = _make_entry("de")
        entry.add_to_hass(hass)
        ent_reg = er.async_get(hass)
        ent_reg.async_get_or_create(
            "sensor",
            DOMAIN,
            "polleninformation_hamburg_birch",
            suggested_object_id="polleninformation_hamburg_birch",
            config_entry=entry,
        )
        with _frozen(moment):
            entities = await _setup_entities(
                hass,
                "de",
                entry=entry,
                response=EMPTY_RESPONSE,
                language_block=EMPTY_LANGUAGE_BLOCK,
            )
        return _by_type(entities, PolleninformationSensor)

    async def test_second_outage_gets_a_fresh_timestamp(self, hass):
        sensor = await self._recreated_at(hass, T1)
        with _frozen(T1):
            assert sensor.extra_state_attributes["stale_since"] == T1.isoformat()

        sensor.coordinator.data = GERMAN_BIRCH_RESPONSE
        with _frozen(T1):
            assert "stale_since" not in sensor.extra_state_attributes

        sensor.coordinator.data = EMPTY_RESPONSE
        with _frozen(T2):
            attrs = sensor.extra_state_attributes
        assert attrs["data_stale"] is True
        assert attrs["stale_since"] == T2.isoformat()

    async def test_the_timestamp_does_not_drift_across_reads(self, hass):
        """The property is read more than once per update."""
        sensor = await self._recreated_at(hass, T1)
        with _frozen(T1):
            first = sensor.extra_state_attributes["stale_since"]
        with _frozen(T2):
            second = sensor.extra_state_attributes["stale_since"]
        assert first == second == T1.isoformat()

    @pytest.mark.parametrize(
        ("cls", "key", "payload"),
        [
            (AllergyRiskSensor, "allergyrisk", {"allergyrisk_1": 5.0}),
            (
                AllergyRiskHourlySensor,
                "allergyrisk_hourly",
                {"allergyrisk_hourly_1": [5.0] * 24},
            ),
        ],
    )
    async def test_risk_sensors_date_the_current_outage(self, cls, key, payload):
        """The risk sensors froze the same timestamp for the same reason."""
        coordinator = _make_coordinator({key: {}})
        sensor = cls(
            coordinator=coordinator,
            levels_current=["none", "low", "moderate", "high", "very high"],
            location_slug="hamburg",
            location_title="Hamburg",
            is_stale=True,
            stale_since=T1.isoformat(),
        )
        with _frozen(T1):
            assert sensor.extra_state_attributes["stale_since"] == T1.isoformat()

        coordinator.data = {key: payload}
        with _frozen(T1):
            assert "stale_since" not in sensor.extra_state_attributes

        coordinator.data = {key: {}}
        with _frozen(T2):
            attrs = sensor.extra_state_attributes
        assert attrs["data_stale"] is True
        assert attrs["stale_since"] == T2.isoformat()


class TestGenusPrefixedNameOnTheSetupPath:
    """Prose that begins with a latin genus must not be taken for that genus.

    The setup path owns the entity_id and queues the rename, so resolving
    "Ambrosia hojas" to ragweed there does more than mis-match a sensor.
    """

    async def _setup(self, hass, entry=None):
        return await _setup_entities(
            hass,
            "es",
            entry=entry,
            response=GENUS_PREFIXED_NAME_RESPONSE,
            language_block=EMPTY_LANGUAGE_BLOCK,
        )

    async def test_does_not_take_the_ragweed_slug(self, hass):
        entities = await self._setup(hass)
        unique_ids = {e.unique_id for e in entities if e.unique_id}
        assert "polleninformation_hamburg_ragweed" not in unique_ids
        assert "polleninformation_hamburg_ambrosia_hojas" in unique_ids

    async def test_does_not_report_the_prose_as_a_latin_name(self, hass):
        entities = await self._setup(hass)
        sensor = _by_type(entities, PolleninformationSensor)
        assert sensor.extra_state_attributes["name_la"] == ""

    async def test_queues_no_rename_onto_ragweed(self, hass):
        entry = _make_entry("es")
        entry.add_to_hass(hass)
        ent_reg = er.async_get(hass)
        ent_reg.async_get_or_create(
            "sensor",
            DOMAIN,
            "polleninformation_hamburg_ambrosia_hojas",
            suggested_object_id="polleninformation_hamburg_ambrosia_hojas",
            config_entry=entry,
        )
        await self._setup(hass, entry=entry)
        assert (
            ent_reg.async_get_entity_id(
                "sensor", DOMAIN, "polleninformation_hamburg_ambrosia_hojas"
            )
            == "sensor.polleninformation_hamburg_ambrosia_hojas"
        )
        assert (
            ent_reg.async_get_entity_id(
                "sensor", DOMAIN, "polleninformation_hamburg_ragweed"
            )
            is None
        )


class TestPartialDataIsNotFreshData:
    """A sensor with no readable value must not report itself fresh.

    A risk block that is present but carries nothing usable for right now,
    only a later day, a null, or an empty hourly list, left native_value
    unknown while clearing the stale marker.
    """

    LEVELS = ["none", "low", "moderate", "high", "very high"]

    def _risk(self, cls, data, is_stale=True):
        return cls(
            coordinator=_make_coordinator(data),
            levels_current=self.LEVELS,
            location_slug="hamburg",
            location_title="Hamburg",
            is_stale=is_stale,
            stale_since=T1.isoformat(),
        )

    @pytest.mark.parametrize(
        ("cls", "data"),
        [
            (AllergyRiskSensor, {"allergyrisk": {"allergyrisk_2": 5.0}}),
            (AllergyRiskSensor, {"allergyrisk": {"allergyrisk_1": None}}),
            (
                AllergyRiskHourlySensor,
                {"allergyrisk_hourly": {"allergyrisk_hourly_2": [5.0] * 24}},
            ),
            (AllergyRiskHourlySensor, {"allergyrisk_hourly": {}}),
            (
                AllergyRiskHourlySensor,
                {"allergyrisk_hourly": {"allergyrisk_hourly_1": []}},
            ),
        ],
    )
    def test_partial_risk_data_stays_stale(self, cls, data):
        sensor = self._risk(cls, data)
        with _frozen(T2):
            attrs = sensor.extra_state_attributes
        assert sensor.native_value is None
        assert attrs["data_stale"] is True
        assert attrs["stale_since"] == T1.isoformat()

    @pytest.mark.parametrize(
        ("cls", "data"),
        [
            (AllergyRiskSensor, {"allergyrisk": {"allergyrisk_1": 0.0}}),
            (
                AllergyRiskHourlySensor,
                {"allergyrisk_hourly": {"allergyrisk_hourly_1": [0.0] * 24}},
            ),
        ],
    )
    def test_a_zero_reading_is_a_reading(self, cls, data):
        """No risk at all is a real value, not a missing one."""
        sensor = self._risk(cls, data)
        with _frozen(T2):
            attrs = sensor.extra_state_attributes
        assert sensor.native_value == "none"
        assert "data_stale" not in attrs
        assert "stale_since" not in attrs

    def test_repeated_partial_responses_keep_the_first_timestamp(self):
        """Flickering between partial shapes is one outage, not several."""
        sensor = self._risk(
            AllergyRiskSensor, {"allergyrisk": {"allergyrisk_2": 5.0}}, is_stale=False
        )
        with _frozen(T1):
            first = sensor.extra_state_attributes["stale_since"]
        sensor.coordinator.data = {"allergyrisk": {"allergyrisk_1": None}}
        with _frozen(T2):
            second = sensor.extra_state_attributes["stale_since"]
        assert first == second == T1.isoformat()

    def test_an_unusable_pollen_level_is_not_fresh(self):
        """The pollen sensor answers the same question the same way.

        A level outside the level names leaves native_value unknown while the
        forecast is still built, so a forecast alone cannot stand for a
        reading.
        """
        sensor = PolleninformationSensor(
            coordinator=_make_coordinator(
                {
                    "contamination": [
                        {"poll_title": "Birke (Betula)", "contamination_1": 9}
                    ]
                }
            ),
            sensor_type="pollen",
            allergen_name="Birke",
            allergen_en="birch",
            allergen_slug="birch",
            allergen_latin="Betula",
            levels_current=self.LEVELS,
            levels_en=self.LEVELS,
            location_slug="hamburg",
            location_title="Hamburg",
            icon="mdi:tree-outline",
            is_stale=True,
            stale_since=T1.isoformat(),
        )
        with _frozen(T2):
            attrs = sensor.extra_state_attributes
        assert sensor.native_value is None
        assert attrs["forecast"]
        assert attrs["data_stale"] is True
        assert attrs["stale_since"] == T1.isoformat()


GERMAN_LANGUAGE_BLOCK = {"poll_titles": [{"name": "Birke", "latin": "Betula"}]}

LOCALIZED_TITLE_RESPONSE = {
    "contamination": [
        {
            "poll_title": "Birke",
            "contamination_1": 3,
            "contamination_2": 2,
            "contamination_3": 1,
            "contamination_4": 0,
        }
    ],
    "allergyrisk": {},
    "allergyrisk_hourly": {},
}


class TestLocalizedTitleWithoutLatin:
    """The API also sends a localized title with no parenthesized latin name.

    Setup resolves that shape through the language block. A recreated sensor
    has no latin to read and the title is not a latin name either, so it has
    to know the localized name the API will send.
    """

    async def _birch(self, hass):
        return await _recreate_stale(
            hass,
            "de",
            "polleninformation_hamburg_birch",
            language_block=GERMAN_LANGUAGE_BLOCK,
        )

    async def test_recovers_from_a_localized_title(self, hass):
        sensor = await self._birch(hass)
        sensor.coordinator.data = LOCALIZED_TITLE_RESPONSE
        assert sensor.native_value == "hoch"

    async def test_forecast_recovers_from_a_localized_title(self, hass):
        sensor = await self._birch(hass)
        sensor.coordinator.data = LOCALIZED_TITLE_RESPONSE
        forecast = sensor.extra_state_attributes["forecast"]
        assert [day["level"] for day in forecast] == [3, 2, 1, 0]

    async def test_the_recreated_sensor_is_named_in_the_configured_language(self, hass):
        """The name the block carries is also the name the user should see."""
        sensor = await self._birch(hass)
        assert sensor.name == "Birke"

    async def test_the_latin_shape_still_works(self, hass):
        """The block must not displace the language independent match."""
        sensor = await self._birch(hass)
        sensor.coordinator.data = GERMAN_BIRCH_RESPONSE
        assert sensor.native_value == "hoch"

    async def test_an_allergen_the_block_does_not_carry_still_recovers(self, hass):
        """Falling back to the English name keeps the slug match reachable."""
        sensor = await _recreate_stale(
            hass,
            "de",
            "polleninformation_hamburg_tree_of_heaven",
            language_block=GERMAN_LANGUAGE_BLOCK,
        )
        sensor.coordinator.data = BINOMIAL_NAME_RESPONSE
        assert sensor.native_value == "mäßig"


MUGWORT_ENTRY = {
    "poll_title": "Artemisia",
    "contamination_1": 1,
    "contamination_2": 1,
    "contamination_3": 0,
    "contamination_4": 0,
}

COMPOSITE_ENTRY = {
    "poll_title": "Artemisia (Asteraceae)",
    "contamination_1": 3,
    "contamination_2": 2,
    "contamination_3": 2,
    "contamination_4": 1,
}

ASTERACEAE_LANGUAGE_BLOCK = {
    "poll_titles": [
        {"name": "composite family", "latin": "Asteraceae"},
        {"name": "mugwort", "latin": "Artemisia"},
    ]
}


class TestTwoEntriesSharingOneName:
    """Two allergens can share a match key, so the name alone cannot decide.

    "Artemisia (Asteraceae)" and a bare "Artemisia" resolve to different
    slugs, but poll_title_local strips the parenthesized latin, so both
    sensors keep "Artemisia" as their name match key.
    """

    @pytest.mark.parametrize(
        "contamination",
        [
            [MUGWORT_ENTRY, COMPOSITE_ENTRY],
            [COMPOSITE_ENTRY, MUGWORT_ENTRY],
        ],
        ids=["mugwort_first", "composite_first"],
    )
    async def test_each_sensor_reads_its_own_entry(self, hass, contamination):
        entities = await _setup_entities(
            hass,
            "en",
            response={
                "contamination": contamination,
                "allergyrisk": {},
                "allergyrisk_hourly": {},
            },
            language_block=ASTERACEAE_LANGUAGE_BLOCK,
        )
        by_slug = {
            e.unique_id: e for e in entities if isinstance(e, PolleninformationSensor)
        }
        mugwort = by_slug["polleninformation_hamburg_mugwort"]
        composite = by_slug["polleninformation_hamburg_composite_family"]

        assert mugwort.native_value == "low"
        assert composite.native_value == "high"
        assert [d["level"] for d in mugwort.extra_state_attributes["forecast"]] == [
            1,
            1,
            0,
            0,
        ]
        assert [d["level"] for d in composite.extra_state_attributes["forecast"]] == [
            3,
            2,
            2,
            1,
        ]
