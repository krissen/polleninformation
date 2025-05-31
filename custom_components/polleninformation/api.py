""" custom_components/polleninformation/api.py"""
import async_timeout
import logging

from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import POLLENAT_API_URL

_LOGGER = logging.getLogger(__name__)
TIMEOUT = 10
HEADERS = {"accept": "application/json"}


async def async_get_pollenat_data(hass, lat, lon, country, lang):
    """Hämtar pollen-data från polleninformation.at."""
    url = POLLENAT_API_URL.format(lat=lat, lon=lon, country=country, lang=lang)
    session = async_get_clientsession(hass)
    try:
        async with async_timeout.timeout(TIMEOUT):
            response = await session.get(url, headers=HEADERS)
            response.raise_for_status()
            payload = await response.json()
            return payload.get("result", {})
    except Exception as err:
        _LOGGER.error("Fel vid hämtning av polleninformation.at: %s", err)
        return {}

