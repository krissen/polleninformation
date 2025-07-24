"""custom_components/polleninformation/api.py"""
"""API functions for polleninformation.at.

See official API documentation: https://www.polleninformation.at/en/data-interface
"""

import logging

import aiohttp
import async_timeout

_LOGGER = logging.getLogger(__name__)

API_URL = (
    "https://www.polleninformation.at/api/forecast/public"
    "?country={country}"
    "&lang={lang}"
    "&latitude={latitude}"
    "&longitude={longitude}"
    "&apikey={apikey}"
)

async def async_get_pollenat_data(
    hass,
    latitude,
    longitude,
    country,
    lang,
    apikey,
):
    """
    Fetches pollen information data from polleninformation.at using the new API.

    Args:
        hass: Home Assistant instance (for potential async session).
        latitude: Latitude (float).
        longitude: Longitude (float).
        country: Country code, e.g., "SE".
        lang: Language code, e.g., "sv".
        apikey: API key (string).

    Returns:
        dict: JSON response from the API, or None on error.
    """
    url = API_URL.format(
        country=country,
        lang=lang,
        latitude=latitude,
        longitude=longitude,
        apikey=apikey,
    )

    _LOGGER.debug(f"Calling polleninformation.at: {url}")

    try:
        async with async_timeout.timeout(15):
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    headers={
                        "Accept": "application/json, text/plain, */*",
                        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148"
                    }
                ) as resp:
                    resp.raise_for_status()
                    return await resp.json()
    except Exception as e:
        _LOGGER.error(f"Error calling polleninformation.at: {e}")
        return None
