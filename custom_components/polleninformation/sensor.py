# custom_components/polleninformation/sensor.py
"""Sensorplattform för polleninformation.at."""
import logging

from homeassistant.components.sensor import ENTITY_ID_FORMAT
from .entity import PollenEntity
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Sätt upp sensorer från en config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    data = coordinator.data.get("contamination", [])
    if not data:
        _LOGGER.warning("Ingen pollen-data tillgänglig för sensorer")
        return

    sensors = []
    for item in data:
        sensors.append(PollenInformationSensor(item, coordinator, entry))

    async_add_entities(sensors, update_before_add=True)


class PollenInformationSensor(PollenEntity):
    """Representation av en pollen-sensor från polleninformation.at."""

    def __init__(self, item: dict, coordinator, config_entry):
        super().__init__(coordinator, config_entry)
        self._item = item
        # Generera entity_id baserat på poll_title
        title_slug = (
            item.get("poll_title", "").lower()
            .replace(" ", "_")
            .replace("(", "")
            .replace(")", "")
        )
    self.entity_id = ENTITY_ID_FORMAT.format(f"polleninformation_{title_slug}")

    @property
    def name(self):
        """Returnera sensorns namn."""
        return self._item.get("poll_title", "Unknown")

    @property
    def state(self):
        """Returnera dagens pollennivå som text."""
        level = self._item.get("contamination_1", 0)
        labels = ["keine Belastung", "gering", "mäßig", "hoch", "sehr hoch"]
        try:
            return labels[level]
        except (IndexError, TypeError):
            return "unavailable"

    @property
    def extra_state_attributes(self):
        """Extra attribut för sensorn."""
        attrs = {
            "raw_value": self._item.get("contamination_1", 0),
            "title":     self._item.get("poll_title", None),
        }
        # Lägg till attribut från bas-klass (update success och last_updated)
        attrs.update(super().add_state_attributes)
        return attrs

    async def async_update(self):
        """Tvinga uppdatering via koordinatorn."""
        await self._coordinator.async_request_refresh()

