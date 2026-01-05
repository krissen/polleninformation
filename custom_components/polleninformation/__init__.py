"""Init file for polleninformation.at integration (new API version).

Sets up the integration and coordinates data updates using only parameters supported by the new API.
All legacy parameters and imports have been removed.
"""

import logging
from datetime import datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import async_get_pollenat_data
from .const import (
    CONF_APIKEY,
    CONF_COUNTRY,
    CONF_LANG,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    DEFAULT_APIKEY,
    DEFAULT_COUNTRY,
    DEFAULT_LANG,
    DEFAULT_LATITUDE,
    DEFAULT_LONGITUDE,
    DOMAIN,
    PLATFORMS,
)
from .utils import get_country_code_map

DEBUG = True
_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(hours=8)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Initial setup of the integration using config entry."""

    # --- MIGRATION: convert country display names to ISO codes ---

    country_val = entry.data.get(CONF_COUNTRY)
    country_map = get_country_code_map(hass)
    if country_val and country_val not in country_map.values():
        code = country_map.get(country_val)
        if code:
            new_data = dict(entry.data)
            new_data[CONF_COUNTRY] = code
            hass.config_entries.async_update_entry(entry, data=new_data)
            _LOGGER.info(
                f"Migrated country display name '{country_val}' to code '{code}' for entry '{entry.title}'."
            )
    # ------------------------------------------------------------

    hass.data.setdefault(DOMAIN, {})

    # Fetch all required parameters, falling back to defaults
    lat = entry.data.get(CONF_LATITUDE, DEFAULT_LATITUDE)
    lon = entry.data.get(CONF_LONGITUDE, DEFAULT_LONGITUDE)
    country = entry.data.get(CONF_COUNTRY, DEFAULT_COUNTRY)
    lang = entry.data.get(CONF_LANG, DEFAULT_LANG)
    apikey = entry.data.get(CONF_APIKEY, DEFAULT_APIKEY)

    if DEBUG:
        _LOGGER.debug(
            "INIT: Setup entry with lat=%s, lon=%s, country=%s, lang=%s",
            lat,
            lon,
            country,
            lang,
        )

    coordinator = PollenInformationDataUpdateCoordinator(
        hass, lat, lon, country, lang, apikey
    )

    # First refresh to populate data
    try:
        await coordinator.async_config_entry_first_refresh()
    except UpdateFailed as err:
        _LOGGER.error("Error fetching initial data: %s", err)
        raise ConfigEntryNotReady

    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Forward setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.add_update_listener(_async_reload_entry)
    return True


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle config entry reload."""
    await hass.config_entries.async_reload(entry.entry_id)


class PollenInformationDataUpdateCoordinator(DataUpdateCoordinator):
    """Coordinator to fetch data from polleninformation.at."""

    def __init__(self, hass: HomeAssistant, lat, lon, country, lang, apikey):
        """Initialize the data coordinator with API parameters."""
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)
        self.lat = lat
        self.lon = lon
        self.country = country
        self.lang = lang
        self.apikey = apikey
        self.last_updated = None

    def _is_valid_api_response(self, result: dict | None) -> bool:
        if result is None:
            return False
        if not isinstance(result, dict):
            return False
        if "contamination" not in result:
            return False
        if not isinstance(result.get("contamination"), list):
            return False
        return True

    async def _async_update_data(self) -> dict:
        """Fetch latest pollen data from API."""
        if DEBUG:
            _LOGGER.debug(
                "COORDINATOR: Update data with lat=%s, lon=%s, country=%s, lang=%s",
                self.lat,
                self.lon,
                self.country,
                self.lang,
            )
        try:
            result = await async_get_pollenat_data(
                self.hass,
                self.lat,
                self.lon,
                self.country,
                self.lang,
                self.apikey,
            )

            if not self._is_valid_api_response(result):
                raise UpdateFailed(
                    f"Invalid API response for {self.country}: missing or malformed data"
                )

            self.last_updated = datetime.now()
            if DEBUG:
                _LOGGER.debug(
                    "COORDINATOR: API result keys: %s",
                    list(result.keys()),  # type: ignore[union-attr]
                )
            return result  # type: ignore[return-value]
        except UpdateFailed:
            raise
        except Exception as err:
            _LOGGER.error("Error fetching polleninformation.at: %s", err)
            raise UpdateFailed(err) from err
