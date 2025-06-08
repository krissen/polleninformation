""" custom_components/polleninformation/api.py """

import logging

import async_timeout
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import POLLENAT_API_URL

DEBUG = True  # Slå på/av debug-loggning

_LOGGER = logging.getLogger(__name__)
TIMEOUT = 10
HEADERS = {"accept": "application/json"}


async def async_get_pollenat_data(hass, lat, lon, country, country_id, lang, lang_id):
    """Hämtar pollen-data från polleninformation.at."""
    url = POLLENAT_API_URL.format(
        lat=lat,
        lon=lon,
        country=country,
        country_id=country_id,
        lang=lang,
        lang_id=lang_id,
    )
    if DEBUG:
        _LOGGER.debug("Polleninformation: API GET %s", url)
    session = async_get_clientsession(hass)
    try:
        async with async_timeout.timeout(TIMEOUT):
            response = await session.get(url, headers=HEADERS)
            if DEBUG:
                _LOGGER.debug("Polleninformation: Response status: %s", response.status)
            response.raise_for_status()
            payload = await response.json()
            if DEBUG:
                _LOGGER.debug("Polleninformation: API payload: %s", payload)
            return payload.get("result", {})
    except Exception as err:
        _LOGGER.error("Fel vid hämtning av polleninformation.at: %s", err)
        return {}
