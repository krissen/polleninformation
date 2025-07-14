# custom_components/polleninformation/config_flow.py
"""Config flow for polleninformation.at integration (new API version).

See official API documentation: https://www.polleninformation.at/en/data-interface
"""

import logging

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.selector import (LocationSelector,
                                            LocationSelectorConfig)

from .api import async_get_pollenat_data
from .const import DEFAULT_LANG, DOMAIN
from .utils import (async_get_country_options, async_get_language_options,
                    async_load_available_languages)

_LOGGER = logging.getLogger(__name__)
DEBUG = True

class PolleninformationConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for polleninformation.at integration."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Initial step for config flow. User selects country, coordinates via map, language, API key, and location name."""
        errors = {}

        # Load country and language options
        country_options = await async_get_country_options(self.hass)
        lang_options = await async_get_language_options(self.hass)
        _LOGGER.debug("country_options: %r", country_options)
        _LOGGER.debug("lang_options: %r", lang_options)

        # Default values from Home Assistant config
        default_country = next(iter(country_options.keys())) if country_options else None
        default_lang_code = DEFAULT_LANG if DEFAULT_LANG in lang_options else "en"
        default_latitude = self.hass.config.latitude
        default_longitude = self.hass.config.longitude

        # Build config flow schema with map selector for coordinates
        data_schema = vol.Schema({
            vol.Required("country", default=default_country): vol.In(country_options),
            vol.Required("location", default={
                "latitude": default_latitude,
                "longitude": default_longitude,
                "radius": 5000,
            }): LocationSelector(LocationSelectorConfig(radius=True)),
            vol.Required("language", default=default_lang_code): vol.In(lang_options),
            vol.Required("apikey", default=""): str,
            vol.Optional("location_name", default=""): str,
        })

        if user_input is not None:
            country_code = user_input["country"]
            lang_code = user_input["language"]
            apikey = user_input["apikey"].strip()
            location = user_input["location"]
            latitude = location["latitude"]
            longitude = location["longitude"]
            location_name = user_input.get("location_name", "").strip()

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
                _LOGGER.debug("Available langs: %r", langs)
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
                    entry_title = location_name if location_name else f"{country_code} ({latitude},{longitude})"
                    entry_data = {
                        "country": country_code,
                        "latitude": latitude,
                        "longitude": longitude,
                        "lang": lang_code,
                        "apikey": apikey,
                        "location": location_name,
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
                    _LOGGER.debug(
                        "Creating polleninformation entry with data: %s and title: %s",
                        entry_data,
                        entry_title,
                    )
                    return self.async_create_entry(
                        title=entry_title,
                        data=entry_data,
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )
