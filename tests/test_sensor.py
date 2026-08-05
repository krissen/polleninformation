"""Tests for sensor helper functions and sensor classes."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo


from custom_components.polleninformation.sensor import (
    AllergyRiskHourlySensor,
    AllergyRiskSensor,
    PolleninformationSensor,
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
