""" custom_components/polleninformation/sensor.py """
"""Sensors for polleninformation.at integration (new API version).

Supports:
- Allergen sensors with localized and English names, latin name, object_id based on English, icon mapping, levels per language.
- One sensor for allergy risk (daily), one for allergy risk (hourly), with scaled values and forecast attributes.
- All attributes and device info as previously.
- DRY/KISS principles.
- All comments and docstrings in English.

See official API documentation: https://www.polleninformation.at/en/data-interface
"""

import logging
from datetime import datetime, timedelta

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.event import async_track_time_interval

from .api import async_get_pollenat_data
from .const import DEFAULT_LANG, DOMAIN
from .const_levels import LEVELS
from .utils import (async_get_language_block, extract_place_slug,
                    get_allergen_info_by_latin, normalize, slugify,
                    split_location)

DEBUG = True
_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(hours=8)

# Icon maps for allergens and air sensors
ALLERGEN_ICON_MAP = {
    "alder": "mdi:tree-outline",
    "ash": "mdi:tree",
    "beech": "mdi:leaf",
    "birch": "mdi:tree",
    "cypress_family": "mdi:pine-tree",
    "default": "mdi:flower-pollen",
    "elm": "mdi:tree",
    "grasses": "mdi:grass",
    "hazel": "mdi:nature",
    "lime": "mdi:leaf",
    "fungal_spores": "mdi:cloud-alert",
    "mugwort": "mdi:flower-pollen",
    "nettle_family": "mdi:leaf",
    "oak": "mdi:leaf",
    "olive": "mdi:leaf",
    "plane_tree": "mdi:tree",
    "ragweed": "mdi:flower-pollen",
    "rye": "mdi:grain",
    "willow": "mdi:tree",
}

def capitalize_first(s):
    """Capitalize the first letter of the given string."""
    if not s:
        return s
    return s[0].upper() + s[1:]

def pollen_forecast_for_allergen(contamination, allergen_name, levels):
    """Return forecast for one allergen for 4 days.
    Always compare allergen names in lower-case to avoid mismatch due to casing."""
    out = []
    allergen_name_lower = allergen_name.lower()
    for item in contamination:
        poll_title = item.get("poll_title", "").split("(", 1)[0].strip().lower()
        if poll_title == allergen_name_lower:
            for day in range(1, 5):
                val = item.get(f"contamination_{day}", 0)
                level_name = levels[val] if isinstance(val, int) and val < len(levels) else str(val)
                out.append(
                    {
                        "day": day,
                        "level_name": level_name,
                        "level": val,
                    }
                )
            break
    return out

def scale_allergy_risk(value):
    """Scale allergy risk to 0-4 for uniform state."""
    try:
        return int(round(value / 2.5))
    except Exception:
        return None

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up polleninformation sensors from a config entry."""
    data = entry.data
    if DEBUG:
        _LOGGER.debug("Polleninformation: async_setup_entry data: %s", data)
    try:
        lat = data["latitude"]
        lon = data["longitude"]
        country = data["country"]
        lang = data.get("lang", DEFAULT_LANG)
        apikey = data.get("apikey")
        location_title = data.get("location_title")
        # location_slug = data.get("location_slug")
        # Fallback if missing or empty
        if not location_title or location_title.strip() == "":
            # Use same fallback as integrations-title
            from .utils import async_get_country_options
            country_options = await async_get_country_options(hass)
            country_name = country_options.get(country, country)
            lat_str = f"{lat:.4f}" if lat is not None else "?"
            lon_str = f"{lon:.4f}" if lon is not None else "?"
            location_title = f"{country_name} ({lat_str}, {lon_str})"
        location_slug = normalize(location_title)
        _LOGGER.debug("Using slugified location_title: '%s' -> '%s'", location_title, location_slug)
    except KeyError as e:
        _LOGGER.error("Missing config field: %s. Data: %s", e, data)
        return
    coordinator = PollenDataCoordinator(
        hass=hass,
        latitude=lat,
        longitude=lon,
        country=country,
        lang=lang,
        apikey=apikey,
    )
    await coordinator.async_refresh()
    if not coordinator.data:
        _LOGGER.error("No pollen data found during setup.")
        return

    contamination = coordinator.data.get("contamination", [])

    # Language/levels handling
    language_block_current = await async_get_language_block(hass, lang)
    language_block_en = await async_get_language_block(hass, "en")
    levels_current = LEVELS.get(lang, LEVELS.get("en", ["none", "low", "moderate", "high", "very high"]))
    levels_en = LEVELS.get("en", ["none", "low", "moderate", "high", "very high"])

    entities = []

    # Allergen sensors (one per item in contamination)
    for item in contamination:
        poll_title_full = item.get("poll_title", "<unknown>")
        poll_title_local = capitalize_first(poll_title_full.split("(", 1)[0].strip())
        latin = None
        # Extract latin name from parenthesis if present
        if "(" in poll_title_full and ")" in poll_title_full:
            latin = poll_title_full.split("(", 1)[1].split(")", 1)[0].strip()
        # Try to map via language block as previously
        if not latin:
            for allergen in language_block_current.get("poll_titles", []):
                if allergen.get("name") == poll_title_local:
                    latin = allergen.get("latin")
                    break
        allergen_en_obj = get_allergen_info_by_latin(latin, language_block_en) if latin else None
        allergen_en = allergen_en_obj["name"] if allergen_en_obj else poll_title_local
        allergen_la = latin if latin else ""
        slug_en = slugify(allergen_en) if allergen_en else slugify(poll_title_local)
        icon = ALLERGEN_ICON_MAP.get(slug_en, ALLERGEN_ICON_MAP["default"])

        entities.append(
            PolleninformationSensor(
                coordinator=coordinator,
                sensor_type="pollen",
                allergen_name=poll_title_local,
                allergen_en=allergen_en,
                allergen_slug=slug_en,
                allergen_latin=allergen_la,
                levels_current=levels_current,
                levels_en=levels_en,
                location_slug=location_slug,
                location_title=location_title,
                icon=icon,
            )
        )

    # Allergy risk daily sensor (one sensor, state is day 1, forecast is days 2-4)
    allergyrisk = coordinator.data.get("allergyrisk", {})
    if allergyrisk:
        entities.append(
            AllergyRiskSensor(
                coordinator=coordinator,
                allergyrisk=allergyrisk,
                levels_current=levels_current,
                location_slug=location_slug,
                location_title=location_title,
            )
        )

    # Allergy risk hourly sensor (one sensor, state is hour 0 of day 1, forecast is hours/days 2-4)
    allergyrisk_hourly = coordinator.data.get("allergyrisk_hourly", {})
    if allergyrisk_hourly:
        entities.append(
            AllergyRiskHourlySensor(
                coordinator=coordinator,
                allergyrisk_hourly=allergyrisk_hourly,
                levels_current=levels_current,
                location_slug=location_slug,
                location_title=location_title,
            )
        )

    async_add_entities(entities, update_before_add=True)

    async def scheduled_refresh(now):
        await coordinator.async_refresh()
        for entity in entities:
            await entity.async_update_ha_state(force_refresh=True)

    async_track_time_interval(hass, scheduled_refresh, SCAN_INTERVAL)

class PollenDataCoordinator:
    """Coordinator to fetch and cache polleninformation.at API data."""
    def __init__(self, hass, latitude, longitude, country, lang, apikey):
        self.hass = hass
        self.latitude = latitude
        self.longitude = longitude
        self.country = country
        self.lang = lang
        self.apikey = apikey
        self.data = None

    async def async_refresh(self):
        """Fetch latest pollen data from API."""
        try:
            self.data = await async_get_pollenat_data(
                self.hass,
                self.latitude,
                self.longitude,
                self.country,
                self.lang,
                self.apikey,
            )
            if DEBUG:
                _LOGGER.debug("API response data: %s", self.data)
        except Exception as e:
            _LOGGER.error("Failed to fetch pollen data: %s", e)
            self.data = None

class PolleninformationSensor(SensorEntity):
    """Generic sensor for pollen allergen."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator,
        sensor_type,
        allergen_name,
        allergen_en,
        allergen_slug,
        allergen_latin,
        levels_current,
        levels_en,
        location_slug,
        location_title,
        icon,
    ):
        self.coordinator = coordinator
        self.sensor_type = sensor_type
        self._allergen_name = allergen_name
        self._allergen_en = allergen_en
        self._allergen_slug = allergen_slug
        self._allergen_latin = allergen_latin
        self._levels_current = levels_current
        self._levels_en = levels_en
        self._location_slug = location_slug
        self._location_title = location_title
        self._icon = icon
        self._attr_name = allergen_name
        self._attr_unique_id = f"polleninformation_{location_slug}_{allergen_slug}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{location_slug}")},
            "name": f"Polleninformation ({location_title})",
            "manufacturer": "Austrian Pollen Information Service",
        }

    @property
    def unique_id(self):
        return self._attr_unique_id

    @property
    def suggested_object_id(self):
        return self._allergen_slug

    @property
    def icon(self):
        return self._icon

    @property
    def state(self):
        """Return today's contamination level as localized string."""
        contamination = self.coordinator.data.get("contamination", [])
        found = None
        for item in contamination:
            poll_title = item.get("poll_title", "").split("(", 1)[0].strip()
            if poll_title.lower() == self._allergen_name.lower():
                found = item
                break
        if not found:
            return None
        raw_val = found.get("contamination_1", 0)
        try:
            return self._levels_current[raw_val]
        except (IndexError, TypeError):
            return "unavailable"

    @property
    def extra_state_attributes(self):
        """Return attributes including forecasts and names."""
        contamination = self.coordinator.data.get("contamination", [])
        # Build forecast with time, level, level_name
        forecast = []
        base_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        for item in contamination:
            poll_title = item.get("poll_title", "").split("(", 1)[0].strip()
            if poll_title.lower() == self._allergen_name.lower():
                for day in range(1, 5):
                    val = item.get(f"contamination_{day}", 0)
                    # Use localized level name
                    level_name = self._levels_current[val] if isinstance(val, int) and val < len(self._levels_current) else str(val)
                    forecast.append({
                        "time": (base_date + timedelta(days=day-1)).strftime("%Y-%m-%dT%H:%M:%S"),
                        "level": val,
                        "level_name": level_name,
                    })
                break

        today_raw = forecast[0] if forecast else None
        tomorrow_raw = forecast[1] if len(forecast) > 1 else None
        return {
            "forecast": forecast,
            "numeric_state": today_raw["level"] if today_raw else None,
            "named_state": today_raw["level_name"] if today_raw else None,
            "tomorrow_numeric_state": tomorrow_raw["level"] if tomorrow_raw else None,
            "tomorrow_named_state": tomorrow_raw["level_name"] if tomorrow_raw else None,
            "friendly_name": self._allergen_name,
            "name_en": self._allergen_en,
            "name_la": self._allergen_latin,
            "allergen_slug": self._allergen_slug,
            "location_title": self._location_title,
            "location_slug": self._location_slug,
            "type": self.sensor_type,
            "attribution": "Austrian Pollen Information Service",
            "icon": self._icon,
            "levels_current": self._levels_current,
            "levels_en": self._levels_en,
            "update_success": self.coordinator.data is not None,
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    async def async_update(self):
        """Update state and attributes (property-based, so nothing to store)."""
        pass

class AllergyRiskSensor(SensorEntity):
    """Sensor for daily allergy risk (one sensor, with forecast)."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, allergyrisk, levels_current, location_slug, location_title):
        self.coordinator = coordinator
        self._allergyrisk = allergyrisk
        self._levels_current = levels_current
        self._location_slug = location_slug
        self._location_title = location_title
        self._attr_name = "Allergy risk"
        self._attr_unique_id = f"polleninformation_{location_slug}_allergy_risk"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{location_slug}")},
            "name": f"Polleninformation ({location_title})",
            "manufacturer": "Austrian Pollen Information Service",
        }
        self._icon = "mdi:alert"

    @property
    def unique_id(self):
        return self._attr_unique_id

    @property
    def icon(self):
        return self._icon

    @property
    def state(self):
        """Return allergy risk value for day 1, scaled to 0-4."""
        value = self._allergyrisk.get("allergyrisk_1", None)
        return scale_allergy_risk(value) if value is not None else None

    @property
    def extra_state_attributes(self):
        """Return attributes including forecast for days 2-4, named/numeric states."""
        forecast = []
        for day in range(2, 5):
            value = self._allergyrisk.get(f"allergyrisk_{day}", None)
            scaled = scale_allergy_risk(value) if value is not None else None
            named = self._levels_current[scaled] if scaled is not None and scaled < len(self._levels_current) else None
            forecast.append({
                "day": day,
                "value": scaled,
                "named_state": named,
            })
        named_state = (
            self._levels_current[self.state]
            if self.state is not None and self.state < len(self._levels_current)
            else None
        )
        raw_value = self._allergyrisk.get("allergyrisk_1", None)
        return {
            "named_state": named_state,
            "numeric_state": self.state,
            "numeric_state_raw": raw_value,
            "forecast": forecast,
            "location_title": self._location_title,
            "location_slug": self._location_slug,
            "attribution": "Austrian Pollen Information Service",
            "update_success": self.coordinator.data is not None,
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    async def async_update(self):
        pass

class AllergyRiskHourlySensor(SensorEntity):
    """Sensor for hourly allergy risk (one sensor, with forecast)."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, allergyrisk_hourly, levels_current, location_slug, location_title):
        self.coordinator = coordinator
        self._allergyrisk_hourly = allergyrisk_hourly
        self._levels_current = levels_current
        self._location_slug = location_slug
        self._location_title = location_title
        self._attr_name = "Allergy risk hourly"
        self._attr_unique_id = f"polleninformation_{location_slug}_allergy_risk_hourly"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{location_slug}")},
            "name": f"Polleninformation ({location_title})",
            "manufacturer": "Austrian Pollen Information Service",
        }
        self._icon = "mdi:timeline-clock"

    @property
    def unique_id(self):
        return self._attr_unique_id

    @property
    def icon(self):
        return self._icon

    @property
    def state(self):
        """Return allergy risk value for current hour of day 1, scaled to 0-4."""
        now_hour = datetime.now().hour
        values = self._allergyrisk_hourly.get("allergyrisk_hourly_1", [])
        if 0 <= now_hour < len(values):
            value = values[now_hour]
            return scale_allergy_risk(value)
        return None

    @property
    def extra_state_attributes(self):
        """Return attributes including forecast for future hours and days."""
        # Forecast for hours of day 1
        hourly_forecast = []
        values = self._allergyrisk_hourly.get("allergyrisk_hourly_1", [])
        for hour, value in enumerate(values):
            scaled = scale_allergy_risk(value)
            named = self._levels_current[scaled] if scaled is not None and scaled < len(self._levels_current) else None
            hourly_forecast.append({
                "hour": hour,
                "value": scaled,
                "named_state": named,
            })
        # Forecast for days 2-4
        day_forecast = []
        for day in range(2, 5):
            values_day = self._allergyrisk_hourly.get(f"allergyrisk_hourly_{day}", [])
            forecast_day = []
            for hour, value in enumerate(values_day):
                scaled = scale_allergy_risk(value)
                named = self._levels_current[scaled] if scaled is not None and scaled < len(self._levels_current) else None
                forecast_day.append({
                    "hour": hour,
                    "value": scaled,
                    "named_state": named,
                })
            day_forecast.append({
                "day": day,
                "hourly_forecast": forecast_day,
            })
        named_state = self._levels_current[self.state] if self.state is not None and self.state < len(self._levels_current) else None
        return {
            "named_state": named_state,
            "numeric_state": self.state,
            "hourly_forecast": hourly_forecast,
            "day_forecast": day_forecast,
            "location_title": self._location_title,
            "location_slug": self._location_slug,
            "attribution": "Austrian Pollen Information Service",
            "update_success": self.coordinator.data is not None,
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    async def async_update(self):
        pass
