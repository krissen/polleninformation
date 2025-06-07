import logging
from datetime import datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .options_flow import OptionsFlowHandler

from .api import async_get_pollenat_data
from .const import (
    CONF_COUNTRY,
    CONF_LANGUAGE,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    DEFAULT_COUNTRY,
    DEFAULT_LANGUAGE,
    DEFAULT_LATITUDE,
    DEFAULT_LONGITUDE,
    DOMAIN,
    PLATFORMS,
)

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(hours=3)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Initial setup of the integration using config entry."""
    hass.data.setdefault(DOMAIN, {})

    lat = entry.data.get(CONF_LATITUDE, DEFAULT_LATITUDE)
    lon = entry.data.get(CONF_LONGITUDE, DEFAULT_LONGITUDE)
    country = entry.data.get(CONF_COUNTRY, DEFAULT_COUNTRY)
    lang = entry.data.get(CONF_LANGUAGE, DEFAULT_LANGUAGE)

    coordinator = PollenInformationDataUpdateCoordinator(hass, lat, lon, country, lang)

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
        self, hass: HomeAssistant, lat: float, lon: float, country: str, lang: str
    ):
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)
        self.lat = lat
        self.lon = lon
        self.country = country
        self.lang = lang
        self.last_updated = None

    async def _async_update_data(self) -> dict:
        try:
            result = await async_get_pollenat_data(
                self.hass, self.lat, self.lon, self.country, self.lang
            )
            self.last_updated = datetime.now()
            return result  # result innehåller nu {"locationtitle": ..., "contamination": [...]}
        except Exception as err:
            _LOGGER.error("Fel vid hämtning av polleninformation.at: %s", err)
            raise UpdateFailed(err)
