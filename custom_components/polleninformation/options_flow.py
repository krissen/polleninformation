""" custom_components/polleninformation/options_flow.py """
"""Options flow for polleninformation.at integration (new API version).

Allows updating country, language, coordinates, API key, and location name.
API key information and request link are included in the form description.

See official API documentation: https://www.polleninformation.at/en/data-interface
"""

import logging

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.selector import (LocationSelector,
                                            LocationSelectorConfig)

from .const import DEFAULT_LANG, DOMAIN
from .utils import async_get_country_options, async_get_language_options

_LOGGER = logging.getLogger(__name__)
DEBUG = True

class OptionsFlowHandler(config_entries.OptionsFlow):
    """Options flow handler for polleninformation.at integration."""

    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Initial step for options flow."""
        errors = {}
        hass = getattr(self.config_entry, "hass", None)
        country_options = await async_get_country_options(hass)
        lang_options = await async_get_language_options(hass)
        _LOGGER.debug("country_options: %r", country_options)
        _LOGGER.debug("lang_options: %r", lang_options)
        defaults = self.config_entry.options or self.config_entry.data or {}

        ha_lang = None
        ha_config = getattr(hass, "config", None)
        if ha_config:
            ha_lang = getattr(ha_config, "language", None)
        if ha_lang is None and hasattr(hass, "locale"):
            ha_lang = getattr(hass.locale, "language", None)
        if ha_lang is None:
            ha_lang = DEFAULT_LANG
        _LOGGER.debug("HA language: %r", ha_lang)
        default_lang_code = ha_lang if ha_lang in lang_options else "en"
        _LOGGER.debug("Default language code: %r", default_lang_code)

        default_country = defaults.get(
            "country", next(iter(country_options.keys())) if country_options else None
        )
        default_latitude = defaults.get(
            "latitude", hass.config.latitude if hass else None
        )
        default_longitude = defaults.get(
            "longitude", hass.config.longitude if hass else None
        )
        default_language = defaults.get("lang", default_lang_code)
        default_apikey = defaults.get("apikey", "")
        default_location_name = defaults.get("location", "")

        data_schema = vol.Schema(
            {
                vol.Required("country", default=default_country): vol.In(country_options),
                vol.Required(
                    "location",
                    default={
                        "latitude": default_latitude,
                        "longitude": default_longitude,
                        "radius": 5000,
                    },
                ): LocationSelector(LocationSelectorConfig(radius=True)),
                vol.Required("language", default=default_language): vol.In(lang_options),
                vol.Required("apikey", default=default_apikey): str,
                vol.Optional("location_name", default=default_location_name): str,
            }
        )

        api_key_info = (
            "An API key is required for polleninformation.at. "
            "You can request an API key at: https://www.polleninformation.at/en/data-interface/request-an-api-key"
        )

        if user_input is not None:
            country_code = user_input.get("country")
            lang_code = user_input.get("language")
            apikey = user_input.get("apikey", "").strip()
            location = user_input.get("location", {})
            latitude = location.get("latitude")
            longitude = location.get("longitude")
            location_name = user_input.get("location_name", "").strip()

            # Compose a user-facing integration title:
            # If location_name is set, use it.
            # Otherwise, fallback to "Polleninformation <country> (<lat>, <lon>)"
            # where <country> is the full country name from country_options.
            country_name = country_options.get(country_code, country_code)
            if location_name:
                entry_title = location_name
                location_title = location_name
                location_slug = (
                    location_name.lower()
                    .replace(" ", "_")
                    .replace("(", "")
                    .replace(")", "")
                    .replace(",", "")
                )
            else:
                lat_str = f"{latitude:.4f}" if latitude is not None else "?"
                lon_str = f"{longitude:.4f}" if longitude is not None else "?"
                entry_title = f"Polleninformation {country_name} ({lat_str}, {lon_str})"
                location_title = entry_title
                location_slug = (
                    f"{country_name}_{lat_str}_{lon_str}".lower()
                    .replace(" ", "_")
                    .replace("(", "")
                    .replace(")", "")
                    .replace(",", "")
                )

            if not apikey:
                errors["apikey"] = "missing_apikey"
                _LOGGER.error("Missing API key.")
            if country_code not in country_options:
                errors["country"] = "invalid_country"
                _LOGGER.error(
                    "Invalid country selected: %r (valid: %r)",
                    country_code,
                    list(country_options.keys()),
                )
            if lang_code not in lang_options:
                errors["language"] = "invalid_language"
                _LOGGER.error(
                    "Invalid language selected: %r (valid: %r)",
                    lang_code,
                    list(lang_options.keys()),
                )

            if not errors:
                return self.async_create_entry(
                    title=entry_title,
                    data={
                        "country": country_code,
                        "latitude": latitude,
                        "longitude": longitude,
                        "lang": lang_code,
                        "apikey": apikey,
                        "location": location_name,
                        "location_title": location_title,
                        "location_slug": location_slug,
                    },
                )
        return self.async_show_form(
            step_id="init",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={"api_key_info": api_key_info},
        )
