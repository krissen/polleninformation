# custom_components/polleninformation/config_flow.py
"""Config flow for polleninformation.at integration."""

import json
import logging
import os

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE

from .api import async_get_pollenat_data

_LOGGER = logging.getLogger(__name__)
DEBUG = True

DOMAIN = "polleninformation"
AVAILABLE_COUNTRIES_FILE = os.path.join(
    os.path.dirname(__file__), "available_countries.json"
)

DEFAULT_LANG = "de"
DEFAULT_LANG_ID = 0


def split_location(locationtitle):
    """Dela locationtitle till (zip, ort)."""
    import re

    locationtitle = locationtitle.strip()
    parts = locationtitle.split(maxsplit=1)
    if parts and re.match(r"^[A-Za-z0-9\-]+$", parts[0]) and len(parts) == 2:
        return parts[0], parts[1]
    return "", locationtitle


async def async_load_available_countries(hass):
    def _load_sync():
        with open(AVAILABLE_COUNTRIES_FILE, encoding="utf-8") as f:
            return json.load(f)["countries"]

    return await hass.async_add_executor_job(_load_sync)


async def async_get_country_options(hass):
    countries = await async_load_available_countries(hass)
    return {
        c["code"]: c["name"] for c in sorted(countries, key=lambda c: c["name"].lower())
    }


class PolleninformationConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}

        country_options = await async_get_country_options(self.hass)
        default_lat = round(self.hass.config.latitude, 5)
        default_lon = round(self.hass.config.longitude, 5)
        default_country = (
            "SE" if "SE" in country_options else next(iter(country_options))
        )

        if user_input is not None:
            country_code = user_input.get("country")
            try:
                latitude = float(user_input.get("latitude"))
                longitude = float(user_input.get("longitude"))
            except Exception:
                errors["latitude"] = "invalid_latitude"
                errors["longitude"] = "invalid_longitude"
                latitude = longitude = None

            if country_code not in country_options:
                errors["country"] = "invalid_country"
            elif not errors:
                # Hitta rätt country_id
                countries = await async_load_available_countries(self.hass)
                countries_by_code = {c["code"]: c for c in countries}
                country_obj = countries_by_code.get(country_code)
                country_id = country_obj.get("country_id")
                if isinstance(country_id, list):
                    country_id = country_id[0]
                elif not isinstance(country_id, int):
                    errors["country"] = "invalid_country"
                    country_id = None

                if not errors:
                    # Gör API-anrop för att få platsnamn
                    pollen_data = await async_get_pollenat_data(
                        self.hass,
                        latitude,
                        longitude,
                        country_code,
                        country_id,
                        DEFAULT_LANG,
                        DEFAULT_LANG_ID,
                    )
                    location_title = pollen_data.get(
                        "locationtitle", country_options[country_code]
                    )
                    _zip, city = split_location(location_title)
                    entry_title = city if city else location_title

                    entry_data = {
                        "country": country_code,
                        "country_id": country_id,
                        "latitude": latitude,
                        "longitude": longitude,
                        "lang": DEFAULT_LANG,
                        "lang_id": DEFAULT_LANG_ID,
                    }
                    if DEBUG:
                        _LOGGER.debug(
                            "Skapar polleninformation-entry med data: %s och title: %s",
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
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )
