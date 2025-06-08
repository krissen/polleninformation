# custom_components/polleninformation/sensor.py
"""Sensorer för polleninformation.at-integration."""

import logging
from datetime import datetime, timedelta

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.event import async_track_time_interval

from .api import async_get_pollenat_data
from .const import DOMAIN

DEBUG = True
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

ALLERGEN_ICON_MAP = {
    "birch": "mdi:tree",
    "hazel": "mdi:nature",
    "alder": "mdi:tree-outline",
    "oak": "mdi:leaf",
    "grass": "mdi:grass",
    "elm": "mdi:tree",
    "mugwort": "mdi:flower-pollen",
    "ragweed": "mdi:flower-pollen",
    "plane": "mdi:tree",
    "ash": "mdi:tree",
    "lime": "mdi:leaf",
    "beech": "mdi:leaf",
    "rye": "mdi:grain",
    "willow": "mdi:tree",
    "default": "mdi:flower-pollen",
}
AIR_SENSOR_ICON_MAP = {
    "air_quality": "mdi:cloud",
    "dayrisk": "mdi:weather-sunny-alert",
    "ozone": "mdi:molecule",
    "particulate_matter": "mdi:blur",
    "sulphur_dioxide": "mdi:cloud-outline",
    "nitrogen_dioxide": "mdi:weather-windy",
    "temperature": "mdi:thermometer",
}


def slugify(text: str) -> str:
    import re

    text = text.split("(", 1)[0] if "(" in text else text
    text = text.strip().lower()
    text = text.replace("ö", "o").replace("ä", "a").replace("å", "a").replace("ß", "ss")
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"[^a-z0-9_]", "", text)
    return text


def split_location(locationtitle):
    import re

    locationtitle = locationtitle.strip()
    parts = locationtitle.split(maxsplit=1)
    if parts and re.match(r"^[A-Za-z0-9\-]+$", parts[0]) and len(parts) == 2:
        return parts[0], parts[1]
    return "", locationtitle


def extract_place_slug(full_location: str) -> str:
    import re

    full_location = full_location.strip()
    parts = full_location.split(maxsplit=1)
    if parts and re.match(r"^[A-Za-z0-9\-]+$", parts[0]) and len(parts) == 2:
        place_name = parts[1]
    else:
        place_name = full_location
    return slugify(place_name)


def pollen_forecast_for_allergen(data, allergen_german):
    out = []
    contamination = data.get("contamination", [])
    days = [
        ("contamination_1", "Heute"),
        ("contamination_2", data.get("contamination_date_2")),
        ("contamination_3", data.get("contamination_date_3")),
        ("contamination_4", data.get("contamination_date_4")),
    ]
    for field, date_label in days:
        for item in contamination:
            if item.get("poll_title", "").startswith(allergen_german):
                val = item.get(field, 0)
                out.append(
                    {
                        "time": _iso_for_label(date_label),
                        "level_name": LEVELS_EN[val],
                        "level": val,
                    }
                )
                break
    return out


def air_forecast_for_type(data, air_type):
    out = []
    additional = data.get("additionalForecastData", [])
    for day in additional:
        date_label = day.get("date", "")
        day_iso = _iso_for_label(date_label)
        if air_type in day:
            value = day[air_type]
            out.append({"time": day_iso, "level": value, "level_name": str(value)})
    return out


def _iso_for_label(label):
    from datetime import date

    now = datetime.now()
    if label == "Heute":
        d = date.today()
    elif label:
        try:
            d = datetime.strptime(label, "%d.%m").replace(year=now.year)
        except Exception:
            return ""
    else:
        return ""
    return d.strftime("%Y-%m-%dT00:00:00")


async def async_setup_entry(hass, entry, async_add_entities):
    data = entry.data
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

    location_title = coordinator.full_location or ""
    location_zip, location_city = split_location(location_title)
    location_slug = extract_place_slug(location_title)

    # Skapa pollen- och luft-sensorer som subklasser av basklassen
    entities = []
    for item in coordinator.data.get("contamination", []):
        allergen = item.get("poll_title", "<unknown>")
        entities.append(
            PolleninformationSensor(
                coordinator=coordinator,
                sensor_type="pollen",
                allergen=allergen,
                location_slug=location_slug,
                location_title=location_city,
                location_zip=location_zip,
            )
        )

    forecast = coordinator.data.get("additionalForecastData", [])
    if forecast:
        today = forecast[0]
        for key in AIR_SENSOR_ICON_MAP:
            if key in today:
                entities.append(
                    PolleninformationSensor(
                        coordinator=coordinator,
                        sensor_type="air",
                        air_type=key,
                        value=today[key],
                        location_slug=location_slug,
                        location_title=location_city,
                        location_zip=location_zip,
                    )
                )

    async_add_entities(entities, update_before_add=True)

    async def scheduled_refresh(now):
        await coordinator.async_refresh()
        for entity in entities:
            await entity.async_update_ha_state(force_refresh=True)

    async_track_time_interval(hass, scheduled_refresh, SCAN_INTERVAL)


class PollenDataCoordinator:
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


class PolleninformationSensor(SensorEntity):
    """Generisk sensor för både pollen och luft (enligt DRY, KISS, best practice)."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator,
        sensor_type,
        allergen=None,
        air_type=None,
        value=None,
        location_slug=None,
        location_title=None,
        location_zip=None,
    ):
        self.coordinator = coordinator
        self.sensor_type = sensor_type  # "pollen" eller "air"
        self._location_slug = location_slug
        self._location_title = location_title
        self._location_zip = location_zip
        self._allergen = None
        self._air_type = None
        self._value = None

        if sensor_type == "pollen":
            raw_title = allergen
            self._allergen = allergen
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
            self._attr_name = english_part
            self._attr_unique_id = (
                f"polleninformation_{location_slug}_{self._allergen_slug}"
            )
            self._attr_device_info = {
                "identifiers": {(DOMAIN, f"{location_slug}")},
                "name": f"Polleninformation ({location_title})",
                "manufacturer": "Austrian Pollen Information Service",
            }
            self._icon = ALLERGEN_ICON_MAP.get(
                self._allergen_slug, ALLERGEN_ICON_MAP["default"]
            )
        else:
            self._air_type = air_type
            self._value = value
            self._attr_name = air_type.replace("_", " ").capitalize()
            self._attr_unique_id = f"polleninformation_{location_slug}_{air_type}"
            self._attr_device_info = {
                "identifiers": {(DOMAIN, f"{location_slug}")},
                "name": f"Polleninformation ({location_title})",
                "manufacturer": "Austrian Pollen Information Service",
            }
            self._icon = AIR_SENSOR_ICON_MAP.get(air_type, "mdi:cloud")

        self._state = None
        self._attr_extra_state_attributes = {}

    @property
    def unique_id(self):
        return self._attr_unique_id

    @property
    def icon(self):
        return self._icon

    @property
    def device_class(self):
        if self.sensor_type == "air" and self._air_type == "temperature":
            return "temperature"
        if self.sensor_type == "air" and self._air_type in [
            "ozone",
            "particulate_matter",
            "sulphur_dioxide",
            "nitrogen_dioxide",
        ]:
            return "aqi"
        return None

    @property
    def unit_of_measurement(self):
        if self.sensor_type == "air" and self._air_type == "temperature":
            return "°C"
        return None

    @property
    def state(self):
        return self._state

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data or {}
        attribs = self._attr_extra_state_attributes.copy()
        if self.sensor_type == "pollen":
            forecast = pollen_forecast_for_allergen(data, self._name_de)
            today_raw = forecast[0] if forecast else None
            tomorrow_raw = forecast[1] if len(forecast) > 1 else None
            attribs.update(
                {
                    "forecast": forecast,
                    "raw": today_raw,
                    "numeric_state": today_raw["level"] if today_raw else None,
                    "named_state": today_raw["level_name"] if today_raw else None,
                    "tomorrow_raw": tomorrow_raw,
                    "tomorrow_numeric_state": (
                        tomorrow_raw["level"] if tomorrow_raw else None
                    ),
                    "tomorrow_named_state": (
                        tomorrow_raw["level_name"] if tomorrow_raw else None
                    ),
                    "update_success": self.coordinator.data is not None,
                    "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "name_de": self._name_de,
                    "name_en": self._name_en,
                    "name_la": self._name_la,
                    "allergen_slug": self._allergen_slug,
                    "location_title": self._location_title,
                    "location_zip": self._location_zip,
                    "location_slug": self._location_slug,
                    "attribution": "Austrian Pollen Information Service",
                }
            )
        else:
            forecast = air_forecast_for_type(data, self._air_type)
            attribs.update(
                {
                    "forecast": forecast,
                    "location_slug": self._location_slug,
                    "location_title": self._location_title,
                    "type": self._air_type,
                    "attribution": "Austrian Pollen Information Service",
                }
            )
        return attribs

    async def async_update(self):
        data = self.coordinator.data
        if not data:
            self._state = None
            self._attr_extra_state_attributes = {}
            if DEBUG:
                _LOGGER.debug(
                    "Polleninformation: Ingen data för %s",
                    getattr(self, "_name_en", self._air_type),
                )
            return

        if self.sensor_type == "pollen":
            contamination = data.get("contamination", [])
            found = None
            for item in contamination:
                if item.get("poll_title") == self._allergen:
                    found = item
                    break
            if not found:
                self._state = None
                self._attr_extra_state_attributes = {}
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
        else:
            # Luftsensor: ta nuvärde för dagen
            additional = data.get("additionalForecastData", [])
            val = None
            if additional:
                val = additional[0].get(self._air_type)
            self._state = val
            self._attr_extra_state_attributes = {}

        if DEBUG:
            _LOGGER.debug(
                "Polleninformation: Sensor '%s' uppdaterad – state: %s, attribs: %s",
                getattr(self, "_name_en", self._air_type),
                self._state,
                self._attr_extra_state_attributes,
            )
