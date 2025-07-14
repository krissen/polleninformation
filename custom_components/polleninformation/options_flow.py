""" custom_components/polleninformation/options_flow.py """

"""Options flow for polleninformation.at integration (new API version).

Allows updating country, language, location, and API key.
Mentions that an API key is required and provides a link for requesting one.

See official API documentation: https://www.polleninformation.at/en/data-interface
"""

import json
import logging
import os

import voluptuous as vol
from homeassistant import config_entries

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

        # Default language from HA config (two-letter ISO code)
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
        default_latitude = defaults.get("latitude", None)
        default_longitude = defaults.get("longitude", None)
        default_language = defaults.get("lang", default_lang_code)
        default_apikey = defaults.get("apikey", "")

        if user_input is not None:
            _LOGGER.debug("User input: %r", user_input)
            country_code = user_input.get("country")
            lang_code = user_input.get("language")
            apikey = user_input.get("apikey", "").strip()
            try:
                latitude = float(user_input.get("latitude"))
                longitude = float(user_input.get("longitude"))
            except Exception:
                errors["latitude"] = "invalid_latitude"
                errors["longitude"] = "invalid_longitude"
                latitude = longitude = None
            _LOGGER.debug(
                "country_code: %r, lang_code: %r, latitude: %r, longitude: %r",
                country_code,
                lang_code,
                latitude,
                longitude,
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
                # Save updated options
                return self.async_create_entry(
                    title=country_options[country_code],
                    data={
                        "country": country_code,
                        "latitude": latitude,
                        "longitude": longitude,
                        "lang": lang_code,
                        "apikey": apikey,
                    },
                )

        data_schema = vol.Schema(
            {
                vol.Required("country", default=default_country): vol.In(
                    country_options
                ),
                vol.Required("latitude", default=default_latitude): float,
                vol.Required("longitude", default=default_longitude): float,
                vol.Required("language", default=default_language): vol.In(
                    lang_options
                ),
                vol.Required("apikey", default=default_apikey): str,
            }
        )

        api_key_info = (
            "An API key is required for polleninformation.at. "
            "You can request an API key at: https://www.polleninformation.at/en/data-interface/request-an-api-key"
        )

        return self.async_show_form(
            step_id="init",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={"api_key_info": api_key_info},
        )
