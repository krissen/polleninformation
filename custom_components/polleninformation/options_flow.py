import json
import os
import voluptuous as vol
from homeassistant import config_entries

DOMAIN = "polleninformation"
AVAILABLE_COUNTRIES_FILE = os.path.join(
    os.path.dirname(__file__), "available_countries.json"
)

def load_available_countries():
    with open(AVAILABLE_COUNTRIES_FILE, encoding="utf-8") as f:
        data = json.load(f)
    return data["countries"]

def get_country_options():
    countries = load_available_countries()
    return {c["code"]: c["name"] for c in countries}

class OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        errors = {}
        country_options = get_country_options()
        defaults = self.config_entry.options or self.config_entry.data

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
                return self.async_create_entry(
                    title=country_options[country_code],
                    data={
                        "country": country_code,
                        "latitude": latitude,
                        "longitude": longitude,
                    }
                )

        data_schema = vol.Schema({
            vol.Required("country", default=defaults.get("country")): vol.In(country_options),
            vol.Required("latitude", default=defaults.get("latitude")): float,
            vol.Required("longitude", default=defaults.get("longitude")): float,
        })

        return self.async_show_form(
            step_id="init",
            data_schema=data_schema,
            errors=errors
        )

