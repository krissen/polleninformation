""" custom_components/polleninformation/sensor.py """
"""Sensorer för polleninformation.at-integration."""

import logging
from datetime import datetime, timedelta

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.event import async_track_time_interval

from .api import async_get_pollenat_data
from .const import DEFAULT_LANG, DEFAULT_LANG_ID, DOMAIN
from .utils import extract_place_slug, slugify, split_location

DEBUG = True
_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(hours=8)

LEVELS_DE = ["keine Belastung", "gering", "mäßig", "hoch", "sehr hoch"]
LEVELS_EN = ["none", "low", "moderate", "high", "very high"]

GERMAN_TO_ENGLISH = {
    "Ambrosia": "Ragweed",
    "Beifuß": "Mugwort",
    "Birke": "Birch",
    "Buche": "Beech",
    "Eiche": "Oak",
    "Erle": "Alder",
    "Esche": "Ash",
    "Gräser": "Grass",
    "Hasel": "Hazel",
    "Linde": "Lime",
    "Nessel- und Glaskraut": "Nettle and pellitory",
    "Pilzsporen": "Mold spores",
    "Platane": "Plane",
    "Roggen": "Rye",
    "Ulme": "Elm",
    "Weide": "Willow",
    "Zypressengewächse": "Cypress",
    "Ölbaum": "Olive",
}

ALLERGEN_ICON_MAP = {
    "alder": "mdi:tree-outline",
    "ash": "mdi:tree",
    "beech": "mdi:leaf",
    "birch": "mdi:tree",
    "cypress": "mdi:pine-tree",
    "default": "mdi:flower-pollen",
    "elm": "mdi:tree",
    "grass": "mdi:grass",
    "hazel": "mdi:nature",
    "lime": "mdi:leaf",
    "mold_spores": "mdi:cloud-alert",
    "mugwort": "mdi:flower-pollen",
    "nettle_and_pellitory": "mdi:leaf",
    "oak": "mdi:leaf",
    "olive": "mdi:leaf",
    "plane": "mdi:tree",
    "ragweed": "mdi:flower-pollen",
    "rye": "mdi:grain",
    "willow": "mdi:tree",
}
AIR_SENSOR_ICON_MAP = {
    "air_quality": "mdi:cloud",
    "asthma_weather": "mdi:stethoscope",
    "dayrisk": "mdi:weather-sunny-alert",
    "nitrogen_dioxide": "mdi:weather-windy",
    "ozone": "mdi:molecule",
    "particulate_matter": "mdi:blur",
    "sulphur_dioxide": "mdi:cloud-outline",
    "temperature": "mdi:thermometer",
}


def pollen_forecast_for_allergen(result, allergen_german):
    out = []
    contamination = result.get("contamination", [])
    days = [
        ("contamination_1", "Heute"),
        ("contamination_2", result.get("contamination_date_2")),
        ("contamination_3", result.get("contamination_date_3")),
        ("contamination_4", result.get("contamination_date_4")),
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


def air_forecast_for_type(result, air_type):
    out = []
    additional = result.get("additionalForecastData", [])
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
        lang = data.get("lang", DEFAULT_LANG)
        lang_id = data.get("lang_id", DEFAULT_LANG_ID)
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

    result = coordinator.data.get("result", {}) if coordinator.data else {}
    location_title = coordinator.full_location or ""
    location_zip, location_city = split_location(location_title)
    location_slug = extract_place_slug(location_title)

    entities = []
    for item in result.get("contamination", []):
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

    forecast = result.get("additionalForecastData", [])
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
            # locationtitle ligger fortfarande på result-nivå
            result = self.data.get("result", {}) if self.data else {}
            self.full_location = (
                result.get("locationtitle", None) if result else None
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
            if getattr(coordinator, "lang", "de") == "de":
                self._attr_name = german_part
            else:
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
        result = data.get("result", {}) if data else {}
        attribs = self._attr_extra_state_attributes.copy()
        if self.sensor_type == "pollen":
            forecast = pollen_forecast_for_allergen(result, self._name_de)
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
            forecast = air_forecast_for_type(result, self._air_type)
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
        result = data.get("result", {}) if data else {}
        if not result:
            self._state = None
            self._attr_extra_state_attributes = {}
            if DEBUG:
                _LOGGER.debug(
                    "Polleninformation: Ingen data för %s",
                    getattr(self, "_name_en", self._air_type),
                )
            return

        if self.sensor_type == "pollen":
            contamination = result.get("contamination", [])
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
            additional = result.get("additionalForecastData", [])
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

