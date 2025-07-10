""" custom_components/polleninformation/options_flow.py """

"""Options flow för polleninformation.at-integration."""

import json
import os

import voluptuous as vol
from homeassistant import config_entries

from .const import DEFAULT_LANG, DEFAULT_LANG_ID, DOMAIN

AVAILABLE_COUNTRIES_FILE = os.path.join(
    os.path.dirname(__file__), "available_countries.json"
)


def load_available_countries():
    try:
        with open(AVAILABLE_COUNTRIES_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("countries", [])
    except Exception:
        return []


def get_country_options():
    countries = load_available_countries()
    return {c["code"]: c["name"] for c in countries}


def get_country_id(code):
    countries = load_available_countries()
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
        country_options = get_country_options()
        defaults = self.config_entry.options or self.config_entry.data or {}

        if user_input is not None:
            country_code = user_input["country"]
            try:
                latitude = float(user_input["latitude"])
                longitude = float(user_input["longitude"])
            except Exception:
                errors["latitude"] = "invalid_latitude"
                errors["longitude"] = "invalid_longitude"
            if country_code not in country_options:
                errors["country"] = "invalid_country"
            elif not errors:
                # Se till att country_id och språk följer med och uppdateras om landet ändras
                country_id = get_country_id(country_code)
                return self.async_create_entry(
                    title=country_options[country_code],
                    data={
                        "country": country_code,
                        "country_id": country_id,
                        "latitude": latitude,
                        "longitude": longitude,
                        "lang": DEFAULT_LANG,
                        "lang_id": DEFAULT_LANG_ID,
                    },
                )

        data_schema = vol.Schema(
            {
                vol.Required("country", default=defaults.get("country")): vol.In(
                    country_options
                ),
                vol.Required("latitude", default=defaults.get("latitude")): float,
                vol.Required("longitude", default=defaults.get("longitude")): float,
            }
        )

        return self.async_show_form(
            step_id="init", data_schema=data_schema, errors=errors
        )
