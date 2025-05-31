# custom_components/polleninformation/sensor.py
"""Sensorplattform för polleninformation.at."""

import logging
import re

from homeassistant.components.sensor import ENTITY_ID_FORMAT
from .const import DOMAIN
from .entity import PollenEntity

_LOGGER = logging.getLogger(__name__)


def slugify(text: str) -> str:
    """
    Gör en enkel slugifiering:
    - Klipper av vid första parentes (tar bort latinskt namn).
    - Gemener, ersätter ö,ä,å med o,a,a och ß med ss.
    - Ersätter mellanslag med underscore.
    - Tar bort allt som inte är a–z, 0–9 eller underscore.
    """
    # Klipp av vid parentes, om sådan finns
    if "(" in text:
        text = text.split("(", 1)[0]
    text = text.strip().lower()
    # Ersätt tyska specialtecken
    text = (
        text.replace("ö", "o")
            .replace("ä", "a")
            .replace("å", "a")
            .replace("ß", "ss")
    )
    # Ersätt mellanslag (och flera) med underscore
    text = re.sub(r"\s+", "_", text)
    # Ta bort allt som inte är a–z, 0–9 eller underscore
    text = re.sub(r"[^a-z0-9_]", "", text)
    return text


async def async_setup_entry(hass, entry, async_add_entities):
    """Sätt upp sensorer från en config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    # Hämta pollen-data, som är en lista av dicts under "contamination"
    data = coordinator.data.get("contamination", [])
    if not data:
        _LOGGER.warning("Ingen pollen-data tillgänglig för sensorer")
        return

    sensors = []
    for item in data:
        sensors.append(PollenInformationSensor(item, coordinator, entry))

    # Lägg till alla sensorer på en gång
    async_add_entities(sensors, update_before_add=True)


class PollenInformationSensor(PollenEntity):
    """Representation av en pollen-sensor från polleninformation.at."""

    def __init__(self, item: dict, coordinator, config_entry):
        super().__init__(coordinator, config_entry)
        self._item = item

        # Hämta hela platsnamnet från koordinatorns data (t.ex. "9020 Klagenfurt")
        full_location = coordinator.data.get("locationtitle", "Unknown Location").strip()
        parts = full_location.split()
        # Ta bort första token om den endast består av siffror (postnummer)
        if parts and parts[0].isdigit():
            place_name = " ".join(parts[1:])
        else:
            place_name = full_location
        location_slug = slugify(place_name)

        # Poll_title kan vara t.ex. "Beifuß (Artemisia)"
        raw_title = item.get("poll_title", "")
        # Dela upp på parentes: tyska + latinska namn
        if "(" in raw_title and ")" in raw_title:
            german_part = raw_title.split("(", 1)[0].strip()
            latin_part = raw_title.split("(", 1)[1].split(")", 1)[0].strip()
        else:
            german_part = raw_title.strip()
            latin_part = ""

        # Slugifiera det tyska namnet
        allergen_slug = slugify(german_part)

        # Sätt entity_id med plats och tyska allergen
        # Exempel: polleninformation_klagenfurt_beifuss
        self.entity_id = ENTITY_ID_FORMAT.format(
            f"polleninformation_{location_slug}_{allergen_slug}"
        )

        # Spara latinskt namn i en egenskap för att använda senare i attribut
        self._latin_name = latin_part

        # Spara tyska namnet (utan parentes) för användning i name()
        self._german_name = german_part

    @property
    def name(self):
        """Returnera sensorns vänliga namn (tyska namnet)."""
        return self._german_name or "Unknown"

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
            "title":     self._item.get("poll_title"),     # original med tyska + latinska
            "latin_name": self._latin_name,                 # enbart latinskt namn
        }
        # Lägg till attrib från bas-klass (update_success och last_updated)
        attrs.update(super().add_state_attributes)
        return attrs

    async def async_update(self):
        """Tvinga en datarush via koordinatorn."""
        await self.coordinator.async_request_refresh()

