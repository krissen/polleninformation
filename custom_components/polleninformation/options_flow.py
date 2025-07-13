""" custom_components/polleninformation/options_flow.py """
"""Options flow för polleninformation.at-integration."""

import json
import os

import voluptuous as vol
from homeassistant import config_entries

from .const import DEFAULT_LANG, DEFAULT_LANG_ID, DOMAIN
from .utils import (async_find_best_lang_key_for_locale,
                    async_get_language_options, async_load_available_languages)

AVAILABLE_COUNTRIES_FILE = os.path.join(
    os.path.dirname(__file__), "available_countries.json"
)

def _sync_load_available_countries():
    try:
        with open(AVAILABLE_COUNTRIES_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("countries", [])
    except Exception:
        return []

async def async_load_available_countries(hass):
    return await hass.async_add_executor_job(_sync_load_available_countries)

def get_country_options_sync():
    countries = _sync_load_available_countries()
    return {c["code"]: c["name"] for c in countries}

async def async_get_country_options(hass):
    countries = await async_load_available_countries(hass)
    return {c["code"]: c["name"] for c in countries}

def get_country_id_sync(code):
    countries = _sync_load_available_countries()
    for c in countries:
        if c.get("code") == code:
            cid = c.get("country_id")
            if isinstance(cid, list) and cid:
                cid = cid[0]
            try:
                return int(cid)
            except Exception:
                continue
    return 1  # fallback

async def async_get_country_id(hass, code):
    countries = await async_load_available_countries(hass)
    for c in countries:
        if c.get("code") == code:
            cid = c.get("country_id")
            if isinstance(cid, list) and cid:
                cid = cid[0]
            try:
                return int(cid)
            except Exception:
                continue
    return 1  # fallback

class OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        errors = {}

        hass = getattr(self.config_entry, "hass", None)
        country_options = await async_get_country_options(hass)
        lang_options = await async_get_language_options(hass)
        defaults = self.config_entry.options or self.config_entry.data or {}

        # Sätt default språk från Home Assistant locale, annars engelska
        ha_locale = getattr(getattr(self.config_entry, "hass", None), "config", None)
        if ha_locale:
            ha_lang = getattr(ha_locale, "language", None)
        else:
            ha_lang = None
        if (
            not ha_lang
            and hasattr(self.config_entry, "hass")
            and hasattr(self.config_entry.hass, "locale")
        ):
            ha_lang = getattr(self.config_entry.hass.locale, "language", None)
        if not ha_lang:
            ha_lang = "en"
        default_lang_key = await async_find_best_lang_key_for_locale(hass, ha_lang)
        if default_lang_key not in lang_options:
            default_lang_key = (
                "1" if "1" in lang_options else next(iter(lang_options.keys()))
            )

        default_country = defaults.get(
            "country", next(iter(country_options.keys())) if country_options else None
        )
        default_latitude = defaults.get("latitude", None)
        default_longitude = defaults.get("longitude", None)
        default_language = defaults.get("lang_id", default_lang_key)

        if user_input is not None:
            country_code = user_input.get("country")
            lang_key = user_input.get("language")
            try:
                latitude = float(user_input.get("latitude"))
                longitude = float(user_input.get("longitude"))
            except Exception:
                errors["latitude"] = "invalid_latitude"
                errors["longitude"] = "invalid_longitude"
                latitude = longitude = None

            if country_code not in country_options:
                errors["country"] = "invalid_country"
            if lang_key not in lang_options:
                errors["language"] = "invalid_language"

            if not errors:
                country_id = await async_get_country_id(hass, country_code)
                langs = await async_load_available_languages(hass)
                selected_lang = next((l for l in langs if l["key"] == lang_key), None)
                if not selected_lang:
                    errors["language"] = "invalid_language"

            if not errors:
                return self.async_create_entry(
                    title=country_options[country_code],
                    data={
                        "country": country_code,
                        "country_id": country_id,
                        "latitude": latitude,
                        "longitude": longitude,
                        "lang": selected_lang["lang_code"],
                        "lang_id": lang_key,
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
            }
        )

        return self.async_show_form(
            step_id="init", data_schema=data_schema, errors=errors
        )
