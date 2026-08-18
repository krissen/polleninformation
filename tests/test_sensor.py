"""Tests for sensor helper functions and sensor classes."""

import logging
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.polleninformation import (
    PollenInformationDataUpdateCoordinator,
)
from custom_components.polleninformation.const import DOMAIN
from custom_components.polleninformation.sensor import (
    ALLERGEN_ICON_MAP,
    KNOWN_ALLERGEN_SLUGS,
    LATIN_NAME_ALIASES,
    LATIN_TO_ENGLISH_NAME,
    RISK_SLUGS,
    AllergyRiskHourlySensor,
    AllergyRiskSensor,
    PolleninformationSensor,
    async_setup_entry,
    canonical_latin,
    capitalize_first,
    english_name_for_latin,
    entity_id_available,
    extract_allergen_slug_from_unique_id,
    localized_risk_object_id_suffixes,
    resolve_latin_alias,
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


T1 = datetime(2026, 8, 18, 6, 0, tzinfo=timezone.utc)
T2 = datetime(2026, 8, 18, 18, 0, tzinfo=timezone.utc)

_UNSET = object()


def _frozen(moment):
    """Patch the sensor module's clock to a fixed moment."""
    return patch(
        "custom_components.polleninformation.sensor.dt_util.now",
        return_value=moment,
    )


def _frozen_util(moment):
    """Patch the coordinator module's clock to a fixed moment."""
    return patch("custom_components.polleninformation.dt_util.now", return_value=moment)


def _make_coordinator(
    data, last_updated=None, last_update_success=True, empty_since=_UNSET
):
    """Create a mock coordinator with the given data.

    empty_since is set by the real coordinator method rather than by a copy
    of its rule, so these tests cannot stay green against a production rule
    that has changed. A test that swaps .data afterwards sets it explicitly,
    which is what the next refresh would do.
    """
    coordinator = MagicMock()
    coordinator.data = data
    coordinator.last_updated = last_updated or datetime.now(timezone.utc)
    coordinator.last_update_success = last_update_success
    coordinator.empty_since = None
    if empty_since is _UNSET:
        with _frozen_util(T1):
            PollenInformationDataUpdateCoordinator._track_empty_response(
                coordinator, data or {}
            )
    else:
        coordinator.empty_since = empty_since
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
        )
        attrs = sensor.extra_state_attributes
        assert attrs["data_stale"] is True
        assert attrs["stale_since"] == T1.isoformat()

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
        )
        assert sensor.native_value is None

    def test_native_value_recovers_from_stale(self, mock_api_response):
        coordinator = _make_coordinator(mock_api_response)
        sensor = AllergyRiskSensor(
            coordinator=coordinator,
            levels_current=["none", "low", "moderate", "high", "very high"],
            location_slug="hamburg",
            location_title="Hamburg",
        )
        # A sensor created during an outage still reads fresh data
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


# The Slovak response spells ragweed's latin name "ambrózia", which is the
# Slovak word rather than a candidate scientific name. Nothing in the static
# map matches it, so before it was declared an alias the allergen was unknown.
SLOVAK_RAGWEED_RESPONSE = {
    "contamination": [
        {
            "poll_title": "Ragweed (ambrózia)",
            "contamination_1": 1,
            "contamination_2": 0,
            "contamination_3": 0,
            "contamination_4": 0,
        }
    ],
    "allergyrisk": {"allergyrisk_1": 5.0},
    "allergyrisk_hourly": {"allergyrisk_hourly_1": [5.0] * 24},
}


class TestDeclaredLatinNameAliases:
    """A spelling declared in LATIN_NAME_ALIASES resolves like the name itself.

    The alias table is an allow-list: only a spelling we have seen the API
    send is rewritten, so an unknown latin name is never guessed at.
    """

    def test_the_alias_resolves_to_its_allergen(self):
        assert english_name_for_latin("ambrózia") == "ragweed"

    def test_the_alias_is_matched_case_insensitively(self):
        assert english_name_for_latin("Ambrózia") == "ragweed"

    def test_the_alias_resolver_rewrites_only_a_declared_alias(self):
        # What the sensor reports as name_la: a declared spelling becomes the
        # name it stands for, and everything else is left exactly as sent,
        # species and all.
        assert resolve_latin_alias("ambrózia") == "Ambrosia"
        assert resolve_latin_alias("Asteraceae") == "Asteraceae"
        assert resolve_latin_alias("Ambrosia artemisiifolia") == (
            "Ambrosia artemisiifolia"
        )
        assert resolve_latin_alias("") == ""
        assert resolve_latin_alias(None) is None

    def test_canonical_latin_returns_the_map_key(self):
        # What anything keyed by latin name has to store, since the language
        # block lookups match exactly.
        assert canonical_latin("ambrózia") == "Ambrosia"
        assert canonical_latin("poaceae") == "Poaceae"
        assert canonical_latin(" Poaceae ") == "Poaceae"
        assert canonical_latin("Ambrosia artemisiifolia") == "Ambrosia"

    def test_canonical_latin_knows_nothing_it_should_not(self):
        assert canonical_latin("Asteraceae") is None
        assert canonical_latin("") is None
        assert canonical_latin(None) is None

    def test_every_alias_names_an_allergen_the_map_knows(self):
        assert set(LATIN_NAME_ALIASES.values()) <= set(LATIN_TO_ENGLISH_NAME)

    def test_no_alias_shadows_a_latin_name_the_map_knows(self):
        # The other half of the same property. Both indexes fold the aliases
        # in with setdefault, so a real latin name wins there, while
        # resolve_latin_alias reads the table directly and lets the alias win.
        # A key that is also a real latin name would therefore make the file
        # and the sensors disagree about the same string, with nothing to warn
        # about it and every test green.
        known = {latin.lower() for latin in LATIN_TO_ENGLISH_NAME}
        known |= {latin.split()[0].lower() for latin in LATIN_TO_ENGLISH_NAME}
        assert not (set(LATIN_NAME_ALIASES) & known)

    def test_the_two_resolvers_agree_on_every_alias(self):
        """What the shadowing rule is for, stated as the property itself."""
        for alias, latin in LATIN_NAME_ALIASES.items():
            assert resolve_latin_alias(alias) == latin
            assert canonical_latin(alias) == latin

    async def _setup(self, hass):
        return await _setup_entities(
            hass,
            "sk",
            response=SLOVAK_RAGWEED_RESPONSE,
            language_block=EMPTY_LANGUAGE_BLOCK,
        )

    async def test_a_slovak_install_gets_the_canonical_slug(self, hass):
        entities = await self._setup(hass)
        unique_ids = {e.unique_id for e in entities if e.unique_id}
        assert "polleninformation_hamburg_ragweed" in unique_ids

    async def test_the_alias_is_reported_as_the_name_it_stands_for(self, hass):
        # Not a canonicalization rule: the alias case is the one where what
        # the API sent and the map key happen to coincide. What the two paths
        # do with a latin name that is not an alias is pinned in
        # TestReportedLatinNameAcrossAnOutage.
        entities = await self._setup(hass)
        sensor = _by_type(entities, PolleninformationSensor)
        assert sensor.extra_state_attributes["name_la"] == "Ambrosia"

    async def test_no_unknown_allergen_warning(self, hass, caplog):
        with caplog.at_level(logging.WARNING):
            await self._setup(hass)
        assert not [r for r in caplog.records if "Unknown allergen" in r.getMessage()]


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

GERMAN_BIRCH_RESPONSE_WITHOUT_LATIN = {
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

    async def test_the_marker_clears_when_the_response_carries_data(self, hass):
        """The marker describes the response, so a response ends it."""
        sensor = await _recreate_stale(hass, "de", "polleninformation_hamburg_birch")
        sensor.coordinator.data = GERMAN_BIRCH_RESPONSE
        sensor.coordinator.empty_since = None
        attrs = sensor.extra_state_attributes
        assert "data_stale" not in attrs
        assert "stale_since" not in attrs

    async def test_an_allergen_missing_from_a_healthy_response_is_unknown(self, hass):
        """One absent allergen is not an outage.

        The response carried data, so nothing about it is stale. This sensor
        simply has no reading, which Home Assistant expresses as unknown.
        """
        sensor = await _recreate_stale(hass, "de", "polleninformation_hamburg_birch")
        sensor.coordinator.data = LATIN_GENUS_AS_NAME_RESPONSE
        sensor.coordinator.empty_since = None
        attrs = sensor.extra_state_attributes
        assert sensor.native_value is None
        # No value means no value: nothing of an earlier reading is kept, so
        # the empty forecast is what says the sensor has nothing to show.
        assert attrs["forecast"] == []
        assert "data_stale" not in attrs
        assert "stale_since" not in attrs

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


class TestAnEntryThatIdentifiesNothingGetsNoSensor:
    """The setup path agrees with the language map generator.

    The test is what the entry identifies, not whether its title can be read:
    "()" is a non-blank title with nothing in either half of it. Such an entry
    names no allergen, so building a sensor from it manufactures an entity
    with no name, no latin name and an entity_id ending in nothing, which no
    later response and no restore path can match back to an allergen. The
    generator refuses to record one; the runtime refuses to build one.
    """

    @staticmethod
    def _response(item):
        return {
            "contamination": [
                item,
                {
                    "poll_title": "Birke (Betula)",
                    "contamination_1": 3,
                    "contamination_2": 2,
                    "contamination_3": 1,
                    "contamination_4": 0,
                },
            ],
            "allergyrisk": {"allergyrisk_1": 5.0},
            "allergyrisk_hourly": {"allergyrisk_hourly_1": [5.0] * 24},
        }

    @pytest.mark.parametrize(
        "item",
        [
            # Nothing to read at all.
            {"poll_title": "", "contamination_1": 1},
            {"poll_title": "   ", "contamination_1": 1},
            {"poll_title": 123, "contamination_1": 1},
            {"contamination_1": 1},
            # Readable, and still naming nothing.
            {"poll_title": "()", "contamination_1": 1},
            {"poll_title": "( )", "contamination_1": 1},
            {"poll_title": "  (  )  ", "contamination_1": 1},
            {"poll_title": "()extra", "contamination_1": 1},
        ],
    )
    async def test_no_sensor_is_built_for_it(self, hass, item):
        entities = await _setup_entities(
            hass,
            "de",
            response=self._response(item),
            language_block=EMPTY_LANGUAGE_BLOCK,
        )
        pollen = [e for e in entities if isinstance(e, PolleninformationSensor)]

        # Only the birch entry beside it became a sensor.
        assert len(pollen) == 1
        assert pollen[0].unique_id == "polleninformation_hamburg_birch"

    @pytest.mark.parametrize("poll_title", ["", "()"])
    async def test_no_entity_id_ending_in_nothing(self, hass, poll_title):
        entities = await _setup_entities(
            hass,
            "de",
            response=self._response({"poll_title": poll_title, "contamination_1": 1}),
            language_block=EMPTY_LANGUAGE_BLOCK,
        )
        unique_ids = {e.unique_id for e in entities if e.unique_id}

        assert "polleninformation_hamburg_" not in unique_ids

    async def test_a_latin_name_alone_is_still_an_allergen(self, hass):
        # The other side of the rule: "(Poaceae)" has no display name in this
        # language, but it identifies an allergen and keeps its sensor.
        entities = await _setup_entities(
            hass,
            "de",
            response=self._response({"poll_title": "(Poaceae)", "contamination_1": 1}),
            language_block=EMPTY_LANGUAGE_BLOCK,
        )
        unique_ids = {e.unique_id for e in entities if e.unique_id}

        assert "polleninformation_hamburg_grasses" in unique_ids

    async def test_it_is_warned_about(self, hass, caplog):
        with caplog.at_level(logging.WARNING):
            await _setup_entities(
                hass,
                "de",
                response=self._response({"poll_title": "", "contamination_1": 1}),
                language_block=EMPTY_LANGUAGE_BLOCK,
            )
        assert [r for r in caplog.records if "identifies no allergen" in r.getMessage()]

    async def test_a_readable_entry_is_untouched(self, hass):
        # The guard may not cost an ordinary allergen its sensor.
        entities = await _setup_entities(hass, "de")
        sensor = _by_type(entities, PolleninformationSensor)
        assert sensor.unique_id == "polleninformation_hamburg_ragweed"


class TestReportedLatinNameAcrossAnOutage:
    """What name_la says on each path, including where they differ.

    The setup path reports what the API sent about this allergen, species
    included. The restore path has only the slug to work from, so the most it
    can say is the key of LATIN_TO_ENGLISH_NAME. For an allergen the API
    spells with a genus alone the two coincide; for one it spells with a
    species they do not, and that difference is deliberate: matching them
    would mean discarding a species the API did send.
    """

    async def test_the_setup_path_reports_the_species_the_api_sent(self, hass):
        entities = await _setup_entities(hass, "de")
        sensor = _by_type(entities, PolleninformationSensor)
        assert sensor.extra_state_attributes["name_la"] == "Ambrosia artemisiifolia"

    async def test_the_restore_path_reports_the_map_key(self, hass):
        sensor = await _recreate_stale(hass, "de", "polleninformation_hamburg_ragweed")
        assert sensor.extra_state_attributes["name_la"] == "Ambrosia"

    async def test_the_difference_lasts_no_longer_than_the_outage(self, hass):
        # The restore path only runs while the API is answering with nothing.
        # The first answer that carries data goes through setup again, so the
        # species comes back with it.
        stale = await _recreate_stale(hass, "de", "polleninformation_hamburg_ragweed")
        assert stale.extra_state_attributes["name_la"] == "Ambrosia"

        entities = await _setup_entities(hass, "de")
        recovered = _by_type(entities, PolleninformationSensor)
        assert recovered.extra_state_attributes["name_la"] == "Ambrosia artemisiifolia"

    async def test_the_paths_agree_when_the_api_sends_the_genus_alone(self, hass):
        # Most allergens, and the reason the difference is easy to miss.
        entities = await _setup_entities(hass, "de", response=GERMAN_BIRCH_RESPONSE)
        setup_sensor = _by_type(entities, PolleninformationSensor)
        stale = await _recreate_stale(hass, "de", "polleninformation_hamburg_birch")

        assert setup_sensor.extra_state_attributes["name_la"] == "Betula"
        assert stale.extra_state_attributes["name_la"] == "Betula"


# A response with entries in it, none of which identify an allergen. The raw
# block is non-empty, so before the emptiness test was moved onto the usable
# entries this looked like a response carrying data while building no sensors
# at all.
ALL_UNUSABLE_RESPONSE = {
    "contamination": [
        {"poll_title": "()", "contamination_1": 1},
        {"poll_title": "", "contamination_1": 2},
        {"contamination_1": 3},
    ],
    "allergyrisk": {},
    "allergyrisk_hourly": {},
}

ALL_UNUSABLE_WITH_RISK_RESPONSE = {
    "contamination": [{"poll_title": "()", "contamination_1": 1}],
    "allergyrisk": {"allergyrisk_1": 5.0},
    "allergyrisk_hourly": {"allergyrisk_hourly_1": [5.0] * 24},
}


class TestABlockOfUnusableEntriesReadsAsEmpty:
    """Entities are kept and marked stale, not lost.

    Every entry in the block identifies nothing, so no sensor is built from
    any of them. Counting the raw list would call that a response carrying
    data, and the sensors this location already has would then simply not be
    added: absent from Home Assistant rather than present and stale, which is
    what the user sees.
    """

    async def _setup_with_registered(self, hass, response, slugs=("birch",)):
        entry = _make_entry("de")
        entry.add_to_hass(hass)
        ent_reg = er.async_get(hass)
        for slug in slugs:
            unique_id = f"polleninformation_hamburg_{slug}"
            ent_reg.async_get_or_create(
                "sensor",
                DOMAIN,
                unique_id,
                suggested_object_id=unique_id,
                config_entry=entry,
            )
        return await _setup_entities(
            hass,
            "de",
            entry=entry,
            response=response,
            language_block=EMPTY_LANGUAGE_BLOCK,
        )

    async def test_a_registered_sensor_is_recreated_rather_than_lost(self, hass):
        entities = await self._setup_with_registered(hass, ALL_UNUSABLE_RESPONSE)
        unique_ids = {e.unique_id for e in entities if e.unique_id}

        assert "polleninformation_hamburg_birch" in unique_ids

    async def test_the_recreated_sensor_is_marked_stale(self, hass):
        entities = await self._setup_with_registered(hass, ALL_UNUSABLE_RESPONSE)
        sensor = _by_type(entities, PolleninformationSensor)

        assert sensor.extra_state_attributes["data_stale"] is True

    async def test_no_sensor_is_built_from_the_unusable_entries(self, hass):
        entities = await self._setup_with_registered(hass, ALL_UNUSABLE_RESPONSE)
        pollen = [e for e in entities if isinstance(e, PolleninformationSensor)]

        # Only the recreated one, nothing manufactured from the junk.
        assert len(pollen) == 1

    async def test_risk_entities_are_recreated_too(self, hass):
        entities = await self._setup_with_registered(
            hass, ALL_UNUSABLE_RESPONSE, slugs=("birch", "allergy_risk")
        )
        unique_ids = {e.unique_id for e in entities if e.unique_id}

        assert "polleninformation_hamburg_allergy_risk" in unique_ids

    async def test_risk_data_keeps_the_response_from_being_stale(self, hass):
        # The two tests are not the same question and are allowed to disagree:
        # the pollen block carried nothing usable, so its sensors are
        # recreated, while the response as a whole did carry data, so nothing
        # is marked stale and the risk sensors report real readings.
        entities = await self._setup_with_registered(
            hass, ALL_UNUSABLE_WITH_RISK_RESPONSE
        )
        sensor = _by_type(entities, PolleninformationSensor)

        assert "data_stale" not in sensor.extra_state_attributes


# One non-object element beside a good one. The coordinator validates that
# contamination is a list and says nothing about what is in it.
NON_OBJECT_ELEMENT_RESPONSE = {
    "contamination": [
        "oops",
        123,
        None,
        ["x"],
        {
            "poll_title": "Birke (Betula)",
            "contamination_1": 3,
            "contamination_2": 2,
            "contamination_3": 1,
            "contamination_4": 0,
        },
    ],
    "allergyrisk": {"allergyrisk_1": 5.0},
    "allergyrisk_hourly": {"allergyrisk_hourly_1": [5.0] * 24},
}


class TestANonObjectEntryCostsOnlyItself:
    """One junk element may not take the whole location down with it.

    Everything else on this branch degrades a single sensor. This one raised
    inside setup, which fails the config entry: every sensor for the location
    disappears, risk sensors included. It raised again on every read, so
    fixing setup alone would not have been enough.
    """

    async def test_setup_survives_and_keeps_the_good_entry(self, hass):
        entities = await _setup_entities(
            hass,
            "de",
            response=NON_OBJECT_ELEMENT_RESPONSE,
            language_block=EMPTY_LANGUAGE_BLOCK,
        )
        unique_ids = {e.unique_id for e in entities if e.unique_id}

        assert "polleninformation_hamburg_birch" in unique_ids

    async def test_the_risk_sensors_survive_too(self, hass):
        entities = await _setup_entities(
            hass,
            "de",
            response=NON_OBJECT_ELEMENT_RESPONSE,
            language_block=EMPTY_LANGUAGE_BLOCK,
        )
        unique_ids = {e.unique_id for e in entities if e.unique_id}

        assert "polleninformation_hamburg_allergy_risk" in unique_ids

    async def test_the_junk_is_warned_about(self, hass, caplog):
        with caplog.at_level(logging.WARNING):
            await _setup_entities(
                hass,
                "de",
                response=NON_OBJECT_ELEMENT_RESPONSE,
                language_block=EMPTY_LANGUAGE_BLOCK,
            )
        skipped = [
            r for r in caplog.records if "identifies no allergen" in r.getMessage()
        ]
        assert len(skipped) == 4

    async def test_reading_the_sensor_survives_it(self, hass):
        # The read path matters as much as setup: the response is re-read on
        # every refresh, so a fix in setup alone would leave the sensor
        # raising for as long as the API sends that element.
        entities = await _setup_entities(
            hass,
            "de",
            response=NON_OBJECT_ELEMENT_RESPONSE,
            language_block=EMPTY_LANGUAGE_BLOCK,
        )
        sensor = _by_type(entities, PolleninformationSensor)

        assert sensor.native_value == "hoch"
        assert len(sensor.extra_state_attributes["forecast"]) == 4


class TestFindItemIsSafeWithoutItsCallers:
    """The block is filtered by _find_item itself, not by its callers.

    These pass today and are meant to: they document the invariant rather
    than fix a reachable bug. _find_item filters the block through the shared
    predicate before either pass, so handing it the raw block directly is
    already safe, and the unpack below that filter cannot meet a None. What
    they pin is that the filter stays inside the function, where it does not
    depend on who calls it.
    """

    @staticmethod
    def _sensor(hass_coordinator):
        return PolleninformationSensor(
            coordinator=hass_coordinator,
            sensor_type="pollen",
            allergen_name="Birke",
            allergen_en="birch",
            allergen_slug="birch",
            allergen_latin="Betula",
            levels_current=["none", "low", "moderate", "high", "very high"],
            levels_en=["none", "low", "moderate", "high", "very high"],
            location_slug="hamburg",
            location_title="Hamburg",
            icon="mdi:tree-outline",
        )

    def test_an_unusable_entry_handed_straight_to_it_is_skipped(self):
        sensor = self._sensor(_make_coordinator({"contamination": []}))
        block = [
            "oops",
            {"poll_title": "()"},
            {"poll_title": 5},
            {},
            {"poll_title": "Birke (Betula)", "contamination_1": 2},
        ]

        # The raw block, unfiltered by any caller.
        assert sensor._find_item(block) == block[-1]

    def test_a_block_of_nothing_usable_finds_nothing(self):
        sensor = self._sensor(_make_coordinator({"contamination": []}))

        assert sensor._find_item(["oops", {"poll_title": "()"}, {}]) is None


class TestABlockThatIsNotAnObject:
    """The same assumption one level up, over the risk blocks.

    allergyrisk and allergyrisk_hourly are read with .get, so a block that
    arrives as a list or a string raised on the first read and took the
    entity down with it. A block that is not an object carries nothing, which
    is what an absent one means too.
    """

    @pytest.mark.parametrize("risk", [["oops"], "x", 42, None])
    async def test_the_daily_risk_sensor_reports_nothing(self, hass, risk):
        entities = await _setup_entities(
            hass,
            "de",
            response={**RAGWEED_RESPONSE, "allergyrisk": risk},
            language_block=EMPTY_LANGUAGE_BLOCK,
        )
        sensor = _by_type(entities, PolleninformationSensor)

        # The pollen sensor is unaffected, and nothing raised on the way here.
        assert sensor.native_value is not None

    @pytest.mark.parametrize("risk", [["oops"], "x", 42])
    async def test_reading_a_risk_sensor_survives_it(self, hass, risk):
        entities = await _setup_entities(hass, "de")
        sensor = _by_type(entities, AllergyRiskSensor)
        sensor.coordinator.data = {**RAGWEED_RESPONSE, "allergyrisk": risk}

        assert sensor.native_value is None
        assert "forecast" not in sensor.extra_state_attributes

    @pytest.mark.parametrize("risk", [["oops"], "x", 42])
    async def test_reading_an_hourly_risk_sensor_survives_it(self, hass, risk):
        entities = await _setup_entities(hass, "de")
        sensor = _by_type(entities, AllergyRiskHourlySensor)
        sensor.coordinator.data = {**RAGWEED_RESPONSE, "allergyrisk_hourly": risk}

        assert sensor.native_value is None


class TestTheRiskGateAtSetup:
    """Risk sensors are gated on the API having SENT pollen data.

    Not on our having read it. An empty contamination block means the API had
    nothing to say and a risk number beside it is meaningless, which is what
    the gate was written for. A block we could not parse is the opposite: the
    forecast was there, we failed at it, and the risk reading is real.
    """

    @staticmethod
    def _response(contamination, **blocks):
        return {
            "contamination": contamination,
            "allergyrisk": {"allergyrisk_1": 7.0},
            "allergyrisk_hourly": {"allergyrisk_hourly_1": [7.0] * 24},
            **blocks,
        }

    async def _setup(self, hass, response):
        return await _setup_entities(
            hass, "de", response=response, language_block=EMPTY_LANGUAGE_BLOCK
        )

    async def test_a_real_reading_survives_a_block_we_could_not_parse(self, hass):
        entities = await self._setup(
            hass, self._response([{"poll_title": "()"}, {"poll_title": ""}])
        )
        unique_ids = {e.unique_id for e in entities if e.unique_id}

        assert "polleninformation_hamburg_allergy_risk" in unique_ids
        assert "polleninformation_hamburg_allergy_risk_hourly" in unique_ids

    async def test_the_reading_is_the_one_the_api_sent(self, hass):
        entities = await self._setup(hass, self._response([{"poll_title": "()"}]))
        sensor = _by_type(entities, AllergyRiskSensor)

        # 7.0 on the API's 0-10 scale, scaled to the 0-4 level names.
        assert sensor.native_value == "hoch"

    async def test_an_empty_block_still_suppresses_them(self, hass):
        # Unchanged, and the reason the gate exists: the API said nothing at
        # all, so a risk number beside it means nothing either.
        entities = await self._setup(hass, self._response([]))
        unique_ids = {e.unique_id for e in entities if e.unique_id}

        assert "polleninformation_hamburg_allergy_risk" not in unique_ids

    async def test_a_risk_block_that_is_not_an_object_builds_no_sensor(self, hass):
        # The fifth emptiness site. This gate kept its own raw read, so a
        # non-object block was truthy here and empty for every other reader:
        # the entity was built and then reported unknown forever.
        entities = await self._setup(
            hass,
            self._response(
                [{"poll_title": "Birke (Betula)", "contamination_1": 1}],
                allergyrisk=["x"],
            ),
        )
        unique_ids = {e.unique_id for e in entities if e.unique_id}

        assert "polleninformation_hamburg_allergy_risk" not in unique_ids
        # The hourly block is fine, so its sensor is unaffected.
        assert "polleninformation_hamburg_allergy_risk_hourly" in unique_ids


class TestEveryEntityReportsTheSameOutage:
    """The timestamp belongs to the response, so siblings must agree on it.

    The per-outage semantics themselves are the coordinator's, and are tested
    in test_init.py. What matters here is that an entity reports the
    coordinator's value rather than one of its own: anything reading
    stale_since off an arbitrary entity of the location gets one answer.
    """

    async def _entities_during_an_outage(self, hass):
        entry = _make_entry("de")
        entry.add_to_hass(hass)
        ent_reg = er.async_get(hass)
        for slug in ("birch", "alder", "allergy_risk", "allergy_risk_hourly"):
            ent_reg.async_get_or_create(
                "sensor",
                DOMAIN,
                f"polleninformation_hamburg_{slug}",
                suggested_object_id=f"polleninformation_hamburg_{slug}",
                config_entry=entry,
            )
        return await _setup_entities(
            hass,
            "de",
            entry=entry,
            response=EMPTY_RESPONSE,
            language_block=EMPTY_LANGUAGE_BLOCK,
        )

    async def test_all_sensor_kinds_report_one_timestamp(self, hass):
        entities = await self._entities_during_an_outage(hass)
        assert len(entities) == 4
        stamps = {e.extra_state_attributes["stale_since"] for e in entities}
        assert stamps == {T1.isoformat()}
        assert all(e.extra_state_attributes["data_stale"] is True for e in entities)

    async def test_the_marker_is_absent_once_the_coordinator_clears_it(self, hass):
        entities = await self._entities_during_an_outage(hass)
        for entity in entities:
            entity.coordinator.data = RAGWEED_RESPONSE
            entity.coordinator.empty_since = None
        for entity in entities:
            assert "data_stale" not in entity.extra_state_attributes


EN_LEVELS = ["none", "low", "moderate", "high", "very high"]

HEALTHY_CONTAMINATION = [{"poll_title": "Birch (Betula)", "contamination_1": 1}]


class TestAMissingReadingIsUnknownNotStale:
    """A response that carried data is never stale, however thin it is.

    A risk block with nothing usable for right now, only a later day, a null,
    or an empty hourly list, leaves the sensor without a value. That is state
    unknown, not an outage: the fetch succeeded and the response had data.
    """

    def _risk(self, cls, block, contamination=None):
        data = {
            "contamination": HEALTHY_CONTAMINATION
            if contamination is None
            else contamination
        }
        data.update(block)
        return cls(
            coordinator=_make_coordinator(data),
            levels_current=EN_LEVELS,
            location_slug="hamburg",
            location_title="Hamburg",
        )

    @pytest.mark.parametrize(
        ("cls", "block"),
        [
            (AllergyRiskSensor, {"allergyrisk": {"allergyrisk_2": 5.0}}),
            (AllergyRiskSensor, {"allergyrisk": {"allergyrisk_1": None}}),
            (AllergyRiskSensor, {"allergyrisk": {}}),
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
    def test_a_thin_risk_block_is_unknown_without_a_marker(self, cls, block):
        sensor = self._risk(cls, block)
        attrs = sensor.extra_state_attributes
        assert sensor.native_value is None
        assert "data_stale" not in attrs
        assert "stale_since" not in attrs

    @pytest.mark.parametrize(
        ("cls", "block"),
        [
            (AllergyRiskSensor, {"allergyrisk": {"allergyrisk_1": 0.0}}),
            (
                AllergyRiskHourlySensor,
                {"allergyrisk_hourly": {"allergyrisk_hourly_1": [0.0] * 24}},
            ),
        ],
    )
    def test_a_zero_reading_is_a_reading(self, cls, block):
        """No risk at all is a real value, not a missing one."""
        sensor = self._risk(cls, block)
        assert sensor.native_value == "none"
        assert "data_stale" not in sensor.extra_state_attributes

    @pytest.mark.parametrize(
        ("cls", "block"),
        [
            (AllergyRiskSensor, {"allergyrisk": {}}),
            (AllergyRiskHourlySensor, {"allergyrisk_hourly": {}}),
        ],
    )
    def test_an_empty_response_still_marks_the_risk_sensors(self, cls, block):
        """The outage itself is response level, and does reach them."""
        sensor = self._risk(cls, block, contamination=[])
        attrs = sensor.extra_state_attributes
        assert sensor.native_value is None
        assert attrs["data_stale"] is True
        assert attrs["stale_since"] == T1.isoformat()

    @pytest.mark.parametrize(
        ("cls", "block"),
        [
            (AllergyRiskSensor, {"allergyrisk": {"allergyrisk_1": 7.5}}),
            (
                AllergyRiskHourlySensor,
                {"allergyrisk_hourly": {"allergyrisk_hourly_1": [7.5] * 24}},
            ),
        ],
    )
    def test_a_risk_only_response_is_not_an_outage(self, cls, block):
        """A reading and a stale marker must never appear together.

        contamination can be empty while the risk blocks carry data, and a
        sensor reporting a current level while advertising data_stale is the
        contradiction the response-level definition exists to prevent.
        """
        sensor = self._risk(cls, block, contamination=[])
        attrs = sensor.extra_state_attributes
        assert sensor.native_value == "high"
        assert "data_stale" not in attrs
        assert "stale_since" not in attrs

    def test_an_unusable_pollen_level_is_unknown_without_a_marker(self):
        """A level the level names do not cover leaves no value either."""
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
            levels_current=EN_LEVELS,
            levels_en=EN_LEVELS,
            location_slug="hamburg",
            location_title="Hamburg",
            icon="mdi:tree-outline",
        )
        attrs = sensor.extra_state_attributes
        assert sensor.native_value is None
        assert attrs["forecast"]
        assert "data_stale" not in attrs


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


class TestGenusPrefixedNameOnTheSetupPath:
    """Prose that begins with a latin genus must not be taken for that genus.

    The setup path owns the entity_id and queues the rename, so resolving
    "Ambrosia hojas" to ragweed there does more than mis-match a sensor. The
    stale-recovery direction is pinned in TestStaleSensorRecovery; this is
    the setup direction of the same rule.
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
