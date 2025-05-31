import logging
import voluptuous as vol

from homeassistant import config_entries
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN,
    CONF_LATITUDE, CONF_LONGITUDE,
    CONF_COUNTRY, CONF_LANGUAGE,
    DEFAULT_LATITUDE, DEFAULT_LONGITUDE,
    DEFAULT_COUNTRY, DEFAULT_LANGUAGE,
)

_LOGGER = logging.getLogger(__name__)


class PollenInformationFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Hantera konfiguration via UI för polleninformation.at."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    async def async_step_user(self, user_input=None):
        """Första och enda steget — samla alla värden."""
        if user_input is not None:
            return self.async_create_entry(
                title="Pollen Information AT",
                data=user_input
            )

        data_schema = vol.Schema({
            vol.Required(CONF_LATITUDE, default=DEFAULT_LATITUDE): cv.latitude,
            vol.Required(CONF_LONGITUDE, default=DEFAULT_LONGITUDE): cv.longitude,
            vol.Required(CONF_COUNTRY, default=DEFAULT_COUNTRY): cv.string,
            vol.Optional(CONF_LANGUAGE, default=DEFAULT_LANGUAGE): cv.string,
        })
        return self.async_show_form(step_id="user", data_schema=data_schema)

