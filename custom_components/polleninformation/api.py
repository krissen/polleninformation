"""API functions for polleninformation.at.

See official API documentation: https://www.polleninformation.at/en/data-interface
"""

import logging

import async_timeout
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)

API_URL = (
    "https://www.polleninformation.at/api/forecast/public"
    "?country={country}"
    "&lang={lang}"
    "&latitude={latitude}"
    "&longitude={longitude}"
    "&apikey={apikey}"
)


class PollenApiError(Exception):
    """Base exception for pollen API errors."""


class PollenApiAuthError(PollenApiError):
    """Invalid or missing API key."""


class PollenApiConnectionError(PollenApiError):
    """Network or connection error."""


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
        dict: JSON response from the API.

    Raises:
        PollenApiAuthError: If API key is invalid.
        PollenApiConnectionError: If network request fails.
        PollenApiError: For other API errors.
    """
    url = API_URL.format(
        country=country,
        lang=lang,
        latitude=latitude,
        longitude=longitude,
        apikey=apikey,
    )

    _LOGGER.debug(
        "Calling polleninformation.at for country=%s, lat=%s, lon=%s",
        country,
        latitude,
        longitude,
    )

    try:
        session = async_get_clientsession(hass)
        async with async_timeout.timeout(15):
            async with session.get(
                url,
                headers={
                    "Accept": "application/json, text/plain, */*",
                    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148",
                },
            ) as resp:
                if resp.status == 401:
                    raise PollenApiAuthError("Invalid API key")
                if resp.status == 403:
                    raise PollenApiAuthError("API key not authorized for this resource")
                resp.raise_for_status()

                data = await resp.json()

                if isinstance(data, dict) and "error" in data:
                    error_msg = data.get("error", "Unknown error")
                    if "api key" in error_msg.lower():
                        raise PollenApiAuthError(error_msg)
                    raise PollenApiError(error_msg)

                return data

    except PollenApiError:
        raise
    except TimeoutError as e:
        raise PollenApiConnectionError(f"Timeout connecting to API: {e}") from e
    except Exception as e:
        _LOGGER.error("Error calling polleninformation.at: %s", e)
        raise PollenApiConnectionError(f"Connection error: {e}") from e
