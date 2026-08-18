"""Tests for integration setup and coordinator."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.polleninformation import (
    PollenInformationDataUpdateCoordinator,
)
from custom_components.polleninformation.const import (
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    MAX_UPDATE_INTERVAL,
    MIN_UPDATE_INTERVAL,
)


class TestCoordinatorValidation:
    """Test _is_valid_api_response."""

    def _make_coordinator(self, hass):
        entry = MockConfigEntry(domain=DOMAIN, title="Test", data={})
        entry.add_to_hass(hass)
        return PollenInformationDataUpdateCoordinator(
            hass, entry, 53.5, 10.0, "DE", "en", "key", timedelta(hours=8)
        )

    def test_none_is_invalid(self, hass):
        c = self._make_coordinator(hass)
        assert c._is_valid_api_response(None) is False

    def test_non_dict_is_invalid(self, hass):
        c = self._make_coordinator(hass)
        assert c._is_valid_api_response("string") is False

    def test_missing_contamination_is_invalid(self, hass):
        c = self._make_coordinator(hass)
        assert c._is_valid_api_response({"foo": "bar"}) is False

    def test_non_list_contamination_is_invalid(self, hass):
        c = self._make_coordinator(hass)
        assert c._is_valid_api_response({"contamination": "not-a-list"}) is False

    def test_valid_response(self, hass):
        c = self._make_coordinator(hass)
        assert c._is_valid_api_response({"contamination": []}) is True


class TestUpdateIntervalClamping:
    """Test that update_interval is properly validated during setup.

    Uses async_setup_entry via config_entries to ensure proper state transitions.
    """

    def _make_entry(self, hass, options_interval=None, data_interval=None):
        data = {
            "country": "DE",
            "latitude": 53.5,
            "longitude": 10.0,
            "lang": "en",
            "apikey": "test-key",
            "location_title": "Hamburg",
            "location_slug": "hamburg",
        }
        options = {}
        if data_interval is not None:
            data["update_interval"] = data_interval
        if options_interval is not None:
            options["update_interval"] = options_interval
        entry = MockConfigEntry(
            domain=DOMAIN, title="Hamburg", data=data, options=options
        )
        entry.add_to_hass(hass)
        return entry

    @patch(
        "custom_components.polleninformation.async_get_pollenat_data",
        new_callable=AsyncMock,
    )
    async def test_default_interval(self, mock_api, hass: HomeAssistant):
        mock_api.return_value = {"contamination": []}
        entry = self._make_entry(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        coordinator = hass.data[DOMAIN][entry.entry_id]
        assert coordinator.update_interval == timedelta(hours=DEFAULT_UPDATE_INTERVAL)

    @patch(
        "custom_components.polleninformation.async_get_pollenat_data",
        new_callable=AsyncMock,
    )
    async def test_options_override_data(self, mock_api, hass: HomeAssistant):
        mock_api.return_value = {"contamination": []}
        entry = self._make_entry(hass, options_interval=4, data_interval=12)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        coordinator = hass.data[DOMAIN][entry.entry_id]
        assert coordinator.update_interval == timedelta(hours=4)

    @patch(
        "custom_components.polleninformation.async_get_pollenat_data",
        new_callable=AsyncMock,
    )
    async def test_clamp_below_min(self, mock_api, hass: HomeAssistant):
        mock_api.return_value = {"contamination": []}
        entry = self._make_entry(hass, options_interval=0)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        coordinator = hass.data[DOMAIN][entry.entry_id]
        assert coordinator.update_interval == timedelta(hours=MIN_UPDATE_INTERVAL)

    @patch(
        "custom_components.polleninformation.async_get_pollenat_data",
        new_callable=AsyncMock,
    )
    async def test_clamp_above_max(self, mock_api, hass: HomeAssistant):
        mock_api.return_value = {"contamination": []}
        entry = self._make_entry(hass, options_interval=100)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        coordinator = hass.data[DOMAIN][entry.entry_id]
        assert coordinator.update_interval == timedelta(hours=MAX_UPDATE_INTERVAL)

    @patch(
        "custom_components.polleninformation.async_get_pollenat_data",
        new_callable=AsyncMock,
    )
    async def test_non_numeric_falls_back(self, mock_api, hass: HomeAssistant):
        mock_api.return_value = {"contamination": []}
        entry = self._make_entry(hass, options_interval="garbage")
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        coordinator = hass.data[DOMAIN][entry.entry_id]
        assert coordinator.update_interval == timedelta(hours=DEFAULT_UPDATE_INTERVAL)


class TestOptionsReloadConsistency:
    """Test that coordinator and sensors use the same effective config."""

    @patch(
        "custom_components.polleninformation.async_get_pollenat_data",
        new_callable=AsyncMock,
    )
    async def test_coordinator_uses_options_over_data(
        self, mock_api, hass: HomeAssistant
    ):
        """Coordinator should reflect options when they differ from data."""
        mock_api.return_value = {"contamination": []}
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="Hamburg",
            data={
                "country": "DE",
                "latitude": 53.5,
                "longitude": 10.0,
                "lang": "en",
                "apikey": "old-key",
                "location_title": "Hamburg",
                "location_slug": "hamburg",
            },
            options={
                "country": "SE",
                "latitude": 59.3,
                "longitude": 18.0,
                "lang": "sv",
                "apikey": "new-key",
                "location_title": "Stockholm",
                "location_slug": "stockholm",
                "update_interval": 4,
            },
        )
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        coordinator = hass.data[DOMAIN][entry.entry_id]
        assert coordinator.country == "SE"
        assert coordinator.lang == "sv"
        assert coordinator.lat == 59.3
        assert coordinator.lon == 18.0
        assert coordinator.apikey == "new-key"
        assert coordinator.update_interval == timedelta(hours=4)


EMPTY_PAYLOAD = {"contamination": []}
FULL_PAYLOAD = {"contamination": [{"poll_title": "Birch (Betula)"}]}

E1 = datetime(2026, 8, 18, 6, 0, tzinfo=timezone.utc)
E2 = datetime(2026, 8, 18, 18, 0, tzinfo=timezone.utc)


def _frozen(moment):
    return patch("custom_components.polleninformation.dt_util.now", return_value=moment)


class TestEmptySince:
    """The coordinator owns response-level staleness.

    data_stale describes the response, not a sensor: it means the fetch
    succeeded and carried nothing usable. Tracking it here gives every entity
    of a location the same timestamp for the same outage.
    """

    def _make_coordinator(self, hass):
        entry = MockConfigEntry(domain=DOMAIN, title="Test", data={})
        entry.add_to_hass(hass)
        return PollenInformationDataUpdateCoordinator(
            hass, entry, 53.5, 10.0, "DE", "en", "key", timedelta(hours=8)
        )

    async def _fetch(self, coordinator, payload, moment):
        with (
            patch(
                "custom_components.polleninformation.async_get_pollenat_data",
                AsyncMock(return_value=payload),
            ),
            _frozen(moment),
        ):
            await coordinator._async_update_data()

    async def test_unset_before_any_fetch(self, hass):
        assert self._make_coordinator(hass).empty_since is None

    async def test_data_leaves_it_unset(self, hass):
        coordinator = self._make_coordinator(hass)
        await self._fetch(coordinator, FULL_PAYLOAD, E1)
        assert coordinator.empty_since is None

    async def test_an_empty_response_stamps_it(self, hass):
        coordinator = self._make_coordinator(hass)
        await self._fetch(coordinator, EMPTY_PAYLOAD, E1)
        assert coordinator.empty_since == E1.isoformat()

    async def test_it_holds_for_the_duration_of_one_outage(self, hass):
        coordinator = self._make_coordinator(hass)
        await self._fetch(coordinator, EMPTY_PAYLOAD, E1)
        await self._fetch(coordinator, EMPTY_PAYLOAD, E2)
        assert coordinator.empty_since == E1.isoformat()

    async def test_recovery_clears_it(self, hass):
        coordinator = self._make_coordinator(hass)
        await self._fetch(coordinator, EMPTY_PAYLOAD, E1)
        await self._fetch(coordinator, FULL_PAYLOAD, E2)
        assert coordinator.empty_since is None

    async def test_a_later_outage_is_stamped_afresh(self, hass):
        coordinator = self._make_coordinator(hass)
        await self._fetch(coordinator, EMPTY_PAYLOAD, E1)
        await self._fetch(coordinator, FULL_PAYLOAD, E1)
        await self._fetch(coordinator, EMPTY_PAYLOAD, E2)
        assert coordinator.empty_since == E2.isoformat()

    async def test_a_failed_fetch_does_not_stamp_it(self, hass):
        """A fetch that never returned says nothing about the response."""
        coordinator = self._make_coordinator(hass)
        with (
            patch(
                "custom_components.polleninformation.async_get_pollenat_data",
                AsyncMock(return_value={"nonsense": True}),
            ),
            _frozen(E1),
        ):
            with pytest.raises(UpdateFailed):
                await coordinator._async_update_data()
        assert coordinator.empty_since is None
