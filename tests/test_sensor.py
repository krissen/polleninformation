"""Tests for sensor helper functions and sensor classes."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.polleninformation.const import DOMAIN
from custom_components.polleninformation.sensor import (
    AllergyRiskHourlySensor,
    AllergyRiskSensor,
    PolleninformationSensor,
    async_setup_entry,
    capitalize_first,
    extract_allergen_slug_from_unique_id,
    pollen_forecast_for_allergen,
    scale_allergy_risk,
)


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


class TestPollenForecast:
    def test_match(self):
        contamination = [
            {
                "poll_title": "Birke (Betula)",
                "contamination_1": 0,
                "contamination_2": 1,
                "contamination_3": 2,
                "contamination_4": 3,
            }
        ]
        levels = ["none", "low", "moderate", "high", "very high"]
        result = pollen_forecast_for_allergen(contamination, "Birke", levels)
        assert len(result) == 4
        assert result[0]["level"] == 0
        assert result[0]["level_name"] == "none"
        assert result[2]["level"] == 2
        assert result[2]["level_name"] == "moderate"

    def test_no_match(self):
        contamination = [{"poll_title": "Birke (Betula)", "contamination_1": 1}]
        levels = ["none", "low"]
        result = pollen_forecast_for_allergen(contamination, "Unknown", levels)
        assert result == []


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


async def _setup_entities(hass, lang, options=None):
    """Run sensor setup for a Ragweed-only response and return the entities."""
    entry = _make_entry(lang, options)
    entry.add_to_hass(hass)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = _make_coordinator(
        RAGWEED_RESPONSE
    )

    entities = []

    def _add(new_entities, update_before_add=False):
        entities.extend(new_entities)

    with patch(
        "custom_components.polleninformation.sensor.async_get_language_block",
        AsyncMock(return_value=RAGWEED_LANGUAGE_BLOCK),
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
