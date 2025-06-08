# custom_components/polleninformation/__init__.py
""" Init file for polleninformation.at integration."""
import logging
from datetime import datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import async_get_pollenat_data
from .const import (
    CONF_COUNTRY,
    CONF_COUNTRY_ID,
    CONF_LANG,
    CONF_LANG_ID,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    DEFAULT_COUNTRY,
    DEFAULT_LANG,
    DEFAULT_LANG_ID,
    DEFAULT_LATITUDE,
    DEFAULT_LONGITUDE,
    DOMAIN,
    PLATFORMS,
)
from .options_flow import OptionsFlowHandler

DEBUG = True
_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(hours=3)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Initial setup of the integration using config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Hämta ALLA nödvändiga parametrar, med fallback till default
    lat = entry.data.get(CONF_LATITUDE, DEFAULT_LATITUDE)
    lon = entry.data.get(CONF_LONGITUDE, DEFAULT_LONGITUDE)
    country = entry.data.get(CONF_COUNTRY, DEFAULT_COUNTRY)
    country_id = entry.data.get(CONF_COUNTRY_ID)
    lang = entry.data.get(CONF_LANG, DEFAULT_LANG)
    lang_id = entry.data.get(CONF_LANG_ID, DEFAULT_LANG_ID)

    if DEBUG:
        _LOGGER.debug(
            "INIT: Setup entry with lat=%s, lon=%s, country=%s, country_id=%s, lang=%s, lang_id=%s",
            lat,
            lon,
            country,
            country_id,
            lang,
            lang_id,
        )

    coordinator = PollenInformationDataUpdateCoordinator(
        hass, lat, lon, country, country_id, lang, lang_id
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


async def async_get_options_flow(config_entry):
    return OptionsFlowHandler(config_entry)


class PollenInformationDataUpdateCoordinator(DataUpdateCoordinator):
    """Coordinator to fetch data from polleninformation.at."""

    def __init__(
        self, hass: HomeAssistant, lat, lon, country, country_id, lang, lang_id
    ):
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)
        self.lat = lat
        self.lon = lon
        self.country = country
        self.country_id = country_id
        self.lang = lang
        self.lang_id = lang_id
        self.last_updated = None

    async def _async_update_data(self) -> dict:
        if DEBUG:
            _LOGGER.debug(
                "COORDINATOR: Update data with lat=%s, lon=%s, country=%s, country_id=%s, lang=%s, lang_id=%s",
                self.lat,
                self.lon,
                self.country,
                self.country_id,
                self.lang,
                self.lang_id,
            )
        try:
            result = await async_get_pollenat_data(
                self.hass,
                self.lat,
                self.lon,
                self.country,
                self.country_id,
                self.lang,
                self.lang_id,
            )
            self.last_updated = datetime.now()
            if DEBUG:
                _LOGGER.debug("COORDINATOR: API result: %s", result)
            return result  # result innehåller nu {"locationtitle": ..., "contamination": [...]}
        except Exception as err:
            _LOGGER.error("Fel vid hämtning av polleninformation.at: %s", err)
            raise UpdateFailed(err)
