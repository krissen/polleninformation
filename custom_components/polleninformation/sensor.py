import logging
from datetime import timedelta

import voluptuous as vol
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_track_time_interval

from .api import async_get_pollenat_data
from .const import (
    CONF_COUNTRY,
    CONF_COUNTRY_ID,
    CONF_LANG,
    CONF_LANG_ID,
    DEFAULT_NAME,
    DOMAIN,
)

DEBUG = True  # Slå på/av debug-loggning

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=60)

LEVELS_DE = ["keine Belastung", "gering", "mäßig", "hoch", "sehr hoch"]
LEVELS_EN = ["none", "low", "moderate", "high", "very high"]

GERMAN_TO_ENGLISH = {
    "Birke": "Birch",
    "Eiche": "Oak",
    "Gräser": "Grass",
    "Erle": "Alder",
    "Hasel": "Hazel",
    "Ulme": "Elm",
    "Weide": "Willow",
    "Buche": "Beech",
    "Beifuß": "Mugwort",
    "Ambrosia": "Ragweed",
    "Esche": "Ash",
    "Roggen": "Rye",
    "Platane": "Plane",
    "Linde": "Lime",
}


def split_location(locationtitle):
    """Dela locationtitle till (zip, ort)."""
    import re

    locationtitle = locationtitle.strip()
    parts = locationtitle.split(maxsplit=1)
    if parts and re.match(r"^[A-Za-z0-9\-]+$", parts[0]) and len(parts) == 2:
        return parts[0], parts[1]
    return "", locationtitle


def slugify(text: str) -> str:
    import re

    if "(" in text:
        text = text.split("(", 1)[0]
    text = text.strip().lower()
    text = text.replace("ö", "o").replace("ä", "a").replace("å", "a").replace("ß", "ss")
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"[^a-z0-9_]", "", text)
    return text


def extract_place_slug(full_location: str) -> str:
    import re

    full_location = full_location.strip()
    parts = full_location.split(maxsplit=1)
    if parts and re.match(r"^[A-Za-z0-9\-]+$", parts[0]) and len(parts) == 2:
        place_name = parts[1]
    else:
        place_name = full_location
    return slugify(place_name)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up pollen sensors from a config entry."""
    data = entry.data
    # Debug: visa all data som förs över till sensorn
    if DEBUG:
        _LOGGER.debug("Polleninformation: async_setup_entry data: %s", data)

    try:
        lat = data["latitude"]
        lon = data["longitude"]
        country = data["country"]
        country_id = data["country_id"]
        lang = data["lang"]
        lang_id = data["lang_id"]
    except KeyError as e:
        _LOGGER.error("Polleninformation: Saknar config-fält: %s. Data: %s", e, data)
        return

    name = data.get("name", DEFAULT_NAME)
    scan_interval = SCAN_INTERVAL

    coordinator = PollenDataCoordinator(
        hass,
        lat=lat,
        lon=lon,
        country=country,
        country_id=country_id,
        lang=lang,
        lang_id=lang_id,
    )
    await coordinator.async_refresh()
    if not coordinator.data:
        _LOGGER.error("No pollen data found during setup.")
        return

    entities = []
    for item in coordinator.data.get("contamination", []):
        allergen = item.get("poll_title", "<unknown>")
        entities.append(
            PollenSensor(
                coordinator,
                allergen=allergen,
                name=name,
            )
        )

    async_add_entities(entities, update_before_add=True)

    async def scheduled_refresh(now):
        await coordinator.async_refresh()
        for entity in entities:
            await entity.async_update_ha_state(force_refresh=True)

    async_track_time_interval(hass, scheduled_refresh, scan_interval)


class PollenDataCoordinator:
    """Samlar och cacher pollen‐data för plats och land."""

    def __init__(self, hass, lat, lon, country, country_id, lang, lang_id):
        self.hass = hass
        self.lat = lat
        self.lon = lon
        self.country = country
        self.country_id = country_id
        self.lang = lang
        self.lang_id = lang_id
        self.data = None
        self.location_slug = None
        self.full_location = None

    async def async_refresh(self):
        if DEBUG:
            _LOGGER.debug(
                "Polleninformation: Anropar API med: lat=%s lon=%s country=%s country_id=%s lang=%s lang_id=%s",
                self.lat,
                self.lon,
                self.country,
                self.country_id,
                self.lang,
                self.lang_id,
            )
        try:
            self.data = await async_get_pollenat_data(
                self.hass,
                self.lat,
                self.lon,
                self.country,
                self.country_id,
                self.lang,
                self.lang_id,
            )
            if DEBUG:
                _LOGGER.debug("Polleninformation: API response data: %s", self.data)
            self.full_location = (
                self.data.get("locationtitle", None) if self.data else None
            )
            self.location_slug = (
                extract_place_slug(self.full_location) if self.full_location else None
            )
            if DEBUG:
                _LOGGER.debug(
                    "Polleninformation: full_location: %s, location_slug: %s",
                    self.full_location,
                    self.location_slug,
                )
        except Exception as e:
            _LOGGER.error("Failed to fetch pollen data: %s", e)
            self.data = None
            self.location_slug = None


class PollenSensor(SensorEntity):
    """En sensor för ett specifikt allergen och plats."""

    def __init__(self, coordinator, allergen, name=None):
        self.coordinator = coordinator
        self._allergen = allergen
        raw_title = allergen
        if "(" in raw_title and ")" in raw_title:
            german_part = raw_title.split("(", 1)[0].strip()
            latin_part = raw_title.split("(", 1)[1].split(")", 1)[0].strip()
        else:
            german_part = raw_title.strip()
            latin_part = ""
        english_part = GERMAN_TO_ENGLISH.get(german_part, latin_part or german_part)
        self._name_de = german_part
        self._name_en = english_part
        self._name_la = latin_part
        self._allergen_slug = slugify(english_part)
        self._location_slug = coordinator.location_slug or "unknown"

        # Extrahera postnummer och ort
        location_title = coordinator.full_location or ""
        location_zip, location_city = split_location(location_title)
        location_title = location_city or location_title.strip()
        self._location_zip = location_zip
        self._location_title = location_title

        # Sätt friendly_name
        self._attr_name = f"Pollen level: {self._name_en.lower()}"
        self._state = None
        self._attr_extra_state_attributes = {}

    @property
    def unique_id(self):
        return f"polleninformation_{self._location_slug}_{self._allergen_slug}"

    @property
    def state(self):
        return self._state

    @property
    def extra_state_attributes(self):
        attribs = self._attr_extra_state_attributes.copy()
        attribs.update(
            {
                "level_de": attribs.get("level_de"),
                "level_en": attribs.get("level_en"),
                "level_index": attribs.get("level_index"),
                "name_de": self._name_de,
                "name_en": self._name_en,
                "name_la": self._name_la,
                "allergen_slug": self._allergen_slug,
                "location_title": self._location_title,
                "location_zip": self._location_zip,
                "location_slug": self._location_slug,
            }
        )
        return attribs

    async def async_update(self):
        data = self.coordinator.data
        if not data:
            self._state = None
            self._attr_extra_state_attributes = {}
            if DEBUG:
                _LOGGER.debug("Polleninformation: Ingen data för %s", self._allergen)
            return

        contamination = data.get("contamination", [])
        found = None
        for item in contamination:
            if item.get("poll_title") == self._allergen:
                found = item
                break
        if not found:
            self._state = None
            self._attr_extra_state_attributes = {}
            if DEBUG:
                _LOGGER.debug(
                    "Polleninformation: Ingen contamination för %s", self._allergen
                )
            return

        raw_val = found.get("contamination_1", 0)
        try:
            level_text_de = LEVELS_DE[raw_val]
        except (IndexError, TypeError):
            level_text_de = "unavailable"
        level_text_en = (
            LEVELS_EN[raw_val] if 0 <= raw_val < len(LEVELS_EN) else "unavailable"
        )
        self._state = level_text_en
        self._attr_extra_state_attributes = {
            "level_de": level_text_de,
            "level_en": level_text_en,
            "level_index": raw_val,
        }
        if DEBUG:
            _LOGGER.debug(
                "Polleninformation: Sensor '%s' uppdaterad – state: %s, attribs: %s",
                self._attr_name,
                self._state,
                self._attr_extra_state_attributes,
            )

        contamination = data.get("contamination", [])
        found = None
        for item in contamination:
            if item.get("poll_title") == self._allergen:
                found = item
                break
        if not found:
            self._state = None
            self._attr_extra_state_attributes = {}
            if DEBUG:
                _LOGGER.debug(
                    "Polleninformation: Ingen contamination för %s", self._allergen
                )
            return

        raw_title = found.get("poll_title", "<unknown>")
        raw_val = found.get("contamination_1", 0)
        if "(" in raw_title and ")" in raw_title:
            german_part = raw_title.split("(", 1)[0].strip()
            latin_part = raw_title.split("(", 1)[1].split(")", 1)[0].strip()
        else:
            german_part = raw_title.strip()
            latin_part = ""
        allergen_slug = slugify(german_part)
        try:
            level_text_de = LEVELS_DE[raw_val]
        except (IndexError, TypeError):
            level_text_de = "unavailable"
        level_text_en = (
            LEVELS_EN[raw_val] if 0 <= raw_val < len(LEVELS_EN) else "unavailable"
        )
        self._state = level_text_en
        self._attr_extra_state_attributes = {
            "level_de": level_text_de,
            "level_en": level_text_en,
            "level_index": raw_val,
            "allergen_slug": allergen_slug,
            "location_title": self.coordinator.full_location,
            "location_slug": self.coordinator.location_slug,
        }
        if DEBUG:
            _LOGGER.debug(
                "Polleninformation: Sensor '%s' uppdaterad – state: %s, attribs: %s",
                self._attr_name,
                self._state,
                self._attr_extra_state_attributes,
            )
