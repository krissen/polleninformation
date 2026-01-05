# custom_components/polleninformation/config_flow.py
"""Config flow for polleninformation.at integration (new API version).

See official API documentation: https://www.polleninformation.at/en/data-interface
"""

import logging

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.selector import LocationSelector, LocationSelectorConfig

from .api import (
    PollenApiAuthError,
    PollenApiConnectionError,
    PollenApiError,
    async_get_pollenat_data,
)
from .const import DEFAULT_LANG, DOMAIN
from .options_flow import OptionsFlowHandler
from .utils import (
    async_get_country_code_from_latlon,
    async_get_country_options,
    async_get_language_options,
    async_load_available_languages,
)

_LOGGER = logging.getLogger(__name__)
DEBUG = True

# Mapping from country code to central coordinates and radius for map zoom
COUNTRY_CENTER = {
    "AT": {"latitude": 47.5, "longitude": 14.0, "radius": 150000},  # Austria
    "CH": {"latitude": 47.0, "longitude": 8.0, "radius": 120000},  # Switzerland
    "DE": {"latitude": 51.0, "longitude": 10.0, "radius": 300000},  # Germany
    "ES": {"latitude": 40.0, "longitude": -4.0, "radius": 350000},  # Spain
    "FR": {"latitude": 46.6, "longitude": 2.2, "radius": 350000},  # France
    "GB": {"latitude": 54.0, "longitude": -2.0, "radius": 300000},  # Great Britain
    "IT": {"latitude": 42.8, "longitude": 12.8, "radius": 250000},  # Italy
    "LT": {"latitude": 55.2, "longitude": 23.8, "radius": 100000},  # Lithuania
    "LV": {"latitude": 56.9, "longitude": 24.6, "radius": 100000},  # Latvia
    "PL": {"latitude": 52.0, "longitude": 19.0, "radius": 200000},  # Poland
    "SE": {"latitude": 62.0, "longitude": 16.0, "radius": 400000},  # Sweden
    "TR": {"latitude": 39.0, "longitude": 35.0, "radius": 400000},  # Turkey
    "UA": {"latitude": 49.0, "longitude": 32.0, "radius": 400000},  # Ukraine
}


class PolleninformationConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for polleninformation.at integration."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Initial step for config flow. User selects country, coordinates via map, language, API key, and location name."""
        errors = {}

        country_options = await async_get_country_options(self.hass)
        lang_options = await async_get_language_options(self.hass)
        _LOGGER.debug("country_options: %r", country_options)
        _LOGGER.debug("lang_options: %r", lang_options)

        # Autodetect defaults from Home Assistant config
        default_latitude = round(self.hass.config.latitude, 5)
        default_longitude = round(self.hass.config.longitude, 5)
        ha_country = getattr(self.hass.config, "country", None)
        if not ha_country:
            ha_country = await async_get_country_code_from_latlon(
                self.hass, default_latitude, default_longitude
            )
        default_country = (
            ha_country
            if ha_country in country_options
            else next(iter(country_options.keys()))
        )
        ha_lang = getattr(self.hass.config, "language", DEFAULT_LANG)
        default_lang_code = ha_lang if ha_lang in lang_options else "en"

        # Use API key from an existing entry if available
        default_apikey = ""
        current_entries = self._async_current_entries()
        if current_entries:
            default_apikey = current_entries[0].data.get("apikey", "")

        # Determine selected country (from user input if present)
        selected_country = default_country
        if (
            user_input is not None
            and "country" in user_input
            and user_input["country"] in country_options
        ):
            selected_country = user_input["country"]

        # Determine location default
        if (
            user_input is not None
            and "country" in user_input
            and user_input["country"] != default_country
            and user_input["country"] in COUNTRY_CENTER
        ):
            location_default = COUNTRY_CENTER[user_input["country"]]
        elif user_input is not None and "location" in user_input:
            location_default = user_input["location"]
        else:
            location_default = {
                "latitude": default_latitude,
                "longitude": default_longitude,
                "radius": 5000,
            }

        # Build config flow schema with map selector for coordinates
        data_schema = vol.Schema(
            {
                vol.Required("country", default=selected_country): vol.In(
                    country_options
                ),
                vol.Optional("location_name", default=""): str,
                vol.Required("location", default=location_default): LocationSelector(
                    LocationSelectorConfig(radius=True)
                ),
                vol.Required("language", default=default_lang_code): vol.In(
                    lang_options
                ),
                vol.Required("apikey", default=default_apikey): str,
            }
        )

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
                    (
                        lang_item
                        for lang_item in langs
                        if lang_item["lang_code"] == lang_code
                    ),
                    None,
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
                    "Calling async_get_pollenat_data with: lat=%r, lon=%r, country=%r, lang=%r",
                    latitude,
                    longitude,
                    country_code,
                    lang_code,
                )
                try:
                    pollen_data = await async_get_pollenat_data(
                        self.hass,
                        latitude,
                        longitude,
                        country_code,
                        lang_code,
                        apikey,
                    )
                except PollenApiAuthError:
                    errors["apikey"] = "invalid_api_key"
                    pollen_data = None
                except PollenApiConnectionError:
                    errors["base"] = "connection_error"
                    pollen_data = None
                except PollenApiError as e:
                    errors["base"] = "api_error"
                    _LOGGER.error("API error: %s", e)
                    pollen_data = None

                _LOGGER.debug("API response: %r", pollen_data)

                if pollen_data is None and not errors:
                    errors["base"] = "no_pollen_data"
                    _LOGGER.error("No pollen data returned for input.")
                elif pollen_data and not pollen_data.get("contamination"):
                    errors["base"] = "no_sensors_for_country"
                    _LOGGER.error(
                        "No contamination sensors for country: %r", country_code
                    )
                else:
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
                        entry_title = f"{country_name} ({lat_str}, {lon_str})"
                        location_title = entry_title
                        location_slug = (
                            f"{country_name}_{lat_str}_{lon_str}".lower()
                            .replace(" ", "_")
                            .replace("(", "")
                            .replace(")", "")
                            .replace(",", "")
                        )

                    entry_data = {
                        "country": country_code,
                        "latitude": latitude,
                        "longitude": longitude,
                        "lang": lang_code,
                        "apikey": apikey,
                        "location": location_name,
                        "location_title": location_title,
                        "location_slug": location_slug,
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

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Return the options flow handler."""
        return OptionsFlowHandler(config_entry)
