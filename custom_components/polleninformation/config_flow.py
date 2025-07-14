""" custom_components/polleninformation/config_flow.py """

"""Config flow for polleninformation.at integration (new API version).

See official API documentation: https://www.polleninformation.at/en/data-interface
"""

import json
import logging
import os

import aiohttp
import voluptuous as vol
from homeassistant import config_entries

from .api import async_get_pollenat_data
from .const import DEFAULT_LANG, DOMAIN
from .utils import (
    async_get_country_options,
    async_get_language_options,
    async_load_available_languages,
    split_location,
)

_LOGGER = logging.getLogger(__name__)
DEBUG = True


async def async_reverse_geocode(lat, lon):
    """
    Reverse geocode latitude and longitude to a place name using Nominatim.
    Returns a string with the place name, or 'Unknown location' on failure.
    """
    url = "https://nominatim.openstreetmap.org/reverse"
    params = {
        "lat": lat,
        "lon": lon,
        "format": "json",
        "zoom": 10,
        "addressdetails": 1,
    }
    headers = {"User-Agent": "Home Assistant Polleninformation Integration"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url, params=params, headers=headers, timeout=5
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    address = result.get("address", {})
                    placename = (
                        address.get("city")
                        or address.get("town")
                        or address.get("village")
                        or address.get("municipality")
                        or address.get("county")
                        or address.get("state")
                    )
                    if placename:
                        return placename
                    # fallback to display_name
                    if result.get("display_name"):
                        return result["display_name"].split(",")[0]
    except Exception as e:
        _LOGGER.warning("Reverse geocoding failed: %s", e)
    return "Unknown location"


class PolleninformationConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Polleninformation integration (new API)."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        # Load country and language options
        country_options = await async_get_country_options(self.hass)
        lang_options = await async_get_language_options(self.hass)
        _LOGGER.debug("country_options: %r", country_options)
        _LOGGER.debug("lang_options: %r", lang_options)

        # Get default lat/lon from HA
        default_lat = round(self.hass.config.latitude, 5)
        default_lon = round(self.hass.config.longitude, 5)

        # Determine default country from HA config or location lookup
        ha_country = getattr(self.hass.config, "country", None)
        default_country = None
        if ha_country and ha_country in country_options:
            default_country = ha_country
        else:
            # Fallback: try to get country from lat/lon via external service
            country_code = None
            try:
                country_code = await async_get_country_code_from_latlon(
                    self.hass, default_lat, default_lon
                )
            except Exception as e:
                _LOGGER.warning("Could not determine country from lat/lon: %s", e)
            if country_code and country_code in country_options:
                default_country = country_code
            elif "SE" in country_options:
                default_country = "SE"
            else:
                default_country = next(iter(country_options))
        _LOGGER.debug("Default country: %r", default_country)

        # Determine default language from HA config (always two-letter ISO code)
        ha_lang = None
        if hasattr(self.hass, "config"):
            ha_lang = getattr(self.hass.config, "language", None)
        if not ha_lang and hasattr(self.hass, "locale"):
            ha_lang = getattr(self.hass.locale, "language", None)
        if not ha_lang:
            ha_lang = DEFAULT_LANG
        _LOGGER.debug("HA language: %r", ha_lang)

        # Use HA language setting if present in lang_options, else fallback to 'en'
        default_lang_code = ha_lang if ha_lang in lang_options else "en"
        _LOGGER.debug("Default language code: %r", default_lang_code)

        # Set default location name by reverse geocoding
        default_location = await async_reverse_geocode(default_lat, default_lon)

        if user_input is not None:
            _LOGGER.debug("User input: %r", user_input)
            country_code = user_input.get("country")
            lang_code = user_input.get("language")
            apikey = user_input.get("apikey", "").strip()
            location_name = user_input.get("location", "").strip()
            try:
                latitude = float(user_input.get("latitude"))
                longitude = float(user_input.get("longitude"))
            except Exception:
                errors["latitude"] = "invalid_latitude"
                errors["longitude"] = "invalid_longitude"
                latitude = longitude = None
            _LOGGER.debug(
                "country_code: %r, lang_code: %r, latitude: %r, longitude: %r, location: %r",
                country_code,
                lang_code,
                latitude,
                longitude,
                location_name,
            )

            # Validate API key
            if not apikey:
                errors["apikey"] = "missing_apikey"
                _LOGGER.error("Missing API key.")

            # Validate country
            if country_code not in country_options:
                errors["country"] = "invalid_country"
                _LOGGER.error(
                    "Invalid country selected: %r (valid: %r)",
                    country_code,
                    list(country_options.keys()),
                )

            # Validate language (must be ISO code)
            if lang_code not in lang_options:
                errors["language"] = "invalid_language"
                _LOGGER.error(
                    "Invalid language selected: %r (valid: %r)",
                    lang_code,
                    list(lang_options.keys()),
                )

            # Confirm that chosen language exists in available languages (lang_code is ISO code)
            if not errors:
                langs = await async_load_available_languages(self.hass)
                _LOGGER.debug(
                    "Available langs (from async_load_available_languages): %r", langs
                )
                selected_lang = next(
                    (l for l in langs if l["lang_code"] == lang_code), None
                )
                if not selected_lang:
                    errors["language"] = "invalid_language"
                    _LOGGER.error(
                        "Selected language '%s' not found in available langs: %r",
                        lang_code,
                        langs,
                    )

            # Validate via API call (only if no previous errors)
            if not errors:
                _LOGGER.debug(
                    "Calling async_get_pollenat_data with: lat=%r, lon=%r, country=%r, lang=%r, apikey=%r",
                    latitude,
                    longitude,
                    country_code,
                    lang_code,
                    apikey,
                )
                pollen_data = await async_get_pollenat_data(
                    self.hass,
                    latitude,
                    longitude,
                    country_code,
                    lang_code,
                    apikey,
                )
                _LOGGER.debug("API response: %r", pollen_data)

                if not pollen_data:
                    errors["base"] = "no_pollen_data"
                    _LOGGER.error("No pollen data returned for input.")
                elif not pollen_data.get("contamination"):
                    errors["base"] = "no_sensors_for_country"
                    _LOGGER.error(
                        "No contamination sensors for country: %r", country_code
                    )
                else:
                    # Use user-provided location name or autodetected
                    location_title = (
                        location_name
                        if location_name
                        else await async_reverse_geocode(latitude, longitude)
                    )
                    entry_title = location_title
                    entry_data = {
                        "country": country_code,
                        "latitude": latitude,
                        "longitude": longitude,
                        "lang": lang_code,
                        "apikey": apikey,
                        "location": location_title,
                    }
                    existing_entries = self._async_current_entries()
                    already_exists = any(
                        e.data.get("country") == country_code
                        and round(e.data.get("latitude", 0), 3) == round(latitude, 3)
                        and round(e.data.get("longitude", 0), 3) == round(longitude, 3)
                        for e in existing_entries
                    )
                    if already_exists:
                        _LOGGER.error(
                            "Configuration already exists for country %s, lat %s, lon %s",
                            country_code,
                            latitude,
                            longitude,
                        )
                        return self.async_abort(reason="already_configured")
                    if DEBUG:
                        _LOGGER.debug(
                            "Creating polleninformation entry with data: %s and title: %s",
                            entry_data,
                            entry_title,
                        )
                    return self.async_create_entry(
                        title=entry_title,
                        data=entry_data,
                    )

        data_schema = vol.Schema(
            {
                vol.Required("country", default=default_country): vol.In(
                    country_options
                ),
                vol.Required("latitude", default=default_lat): float,
                vol.Required("longitude", default=default_lon): float,
                vol.Required("language", default=default_lang_code): vol.In(
                    lang_options
                ),
                vol.Required("apikey", default=""): str,
                vol.Optional("location", default=default_location): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )


async def async_get_country_code_from_latlon(hass, lat, lon):
    """Get ISO country code from latitude/longitude using Nominatim."""
    url = "https://nominatim.openstreetmap.org/reverse"
    params = {
        "lat": lat,
        "lon": lon,
        "format": "json",
        "zoom": 3,
        "addressdetails": 1,
    }
    headers = {"User-Agent": "Home Assistant Polleninformation Integration"}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, headers=headers, timeout=5) as resp:
            if resp.status == 200:
                result = await resp.json()
                return result.get("address", {}).get("country_code", "").upper()
    return None
