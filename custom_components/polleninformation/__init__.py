import logging
from datetime import timedelta, datetime

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import async_get_pollenat_data
from .const import (
    DOMAIN, PLATFORMS,
    CONF_LATITUDE, CONF_LONGITUDE,
    CONF_COUNTRY, CONF_LANGUAGE,
    DEFAULT_LATITUDE, DEFAULT_LONGITUDE,
    DEFAULT_COUNTRY,   DEFAULT_LANGUAGE,
)

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(hours=3)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the integration from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Läsa in konfigurering
    lat = entry.data.get(CONF_LATITUDE, DEFAULT_LATITUDE)
    lon = entry.data.get(CONF_LONGITUDE, DEFAULT_LONGITUDE)
    country = entry.data.get(CONF_COUNTRY, DEFAULT_COUNTRY)
    lang = entry.data.get(CONF_LANGUAGE, DEFAULT_LANGUAGE)

    # Initiera koordinatorn
    coordinator = PollenInformationDataUpdateCoordinator(
        hass, lat, lon, country, lang
    )

    # Gör första uppdatering
    await coordinator.async_config_entry_first_refresh()
    if not coordinator.last_update_success:
        raise ConfigEntryNotReady

    # Spara koordinatorn och ladda plattformar
    hass.data[DOMAIN][entry.entry_id] = coordinator
    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    entry.add_update_listener(_async_reload_entry)
    return True


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)


class PollenInformationDataUpdateCoordinator(DataUpdateCoordinator):
    """Coordinator to fetch data from polleninformation.at."""

    def __init__(
        self,
        hass: HomeAssistant,
        lat: float,
        lon: float,
        country: str,
        lang: str
    ):
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL
        )
        self.lat = lat
        self.lon = lon
        self.country = country
        self.lang = lang
        self.last_updated = None

    async def _async_update_data(self) -> dict:
        """Fetch data from polleninformation.at API."""
        try:
            result = await async_get_pollenat_data(
                self.hass, self.lat, self.lon, self.country, self.lang
            )
            self.last_updated = datetime.now()
            return result
        except Exception as err:
            raise UpdateFailed(err) from err

