"""Sensors for polleninformation.at integration (new API version).

Supports:
- Allergen sensors with localized and English names, latin name, object_id based on English, icon mapping, levels per language.
- One sensor for allergy risk (daily), one for allergy risk (hourly), with scaled values and forecast attributes.
- All attributes and device info as previously.
- DRY/KISS principles.
- All comments and docstrings in English.

See official API documentation: https://www.polleninformation.at/en/data-interface
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_LANG, DOMAIN
from .const_levels import LEVELS
from .utils import (
    async_get_language_block,
    get_allergen_info_by_latin,
    normalize,
    slugify,
)

DEBUG = True
_LOGGER = logging.getLogger(__name__)

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


def capitalize_first(s: str) -> str:
    if not s:
        return s
    return s[0].upper() + s[1:]


def pollen_forecast_for_allergen(
    contamination: list, allergen_name: str, levels: list
) -> list:
    out = []
    allergen_name_lower = allergen_name.lower()
    for item in contamination:
        poll_title = item.get("poll_title", "").split("(", 1)[0].strip().lower()
        if poll_title == allergen_name_lower:
            for day in range(1, 5):
                val = item.get(f"contamination_{day}", 0)
                level_name = (
                    levels[val]
                    if isinstance(val, int) and val < len(levels)
                    else str(val)
                )
                out.append({"day": day, "level_name": level_name, "level": val})
            break
    return out


def scale_allergy_risk(value: Any) -> int | None:
    try:
        return int(round(value / 2.5))
    except Exception:
        return None


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]

    if DEBUG:
        _LOGGER.debug(
            "Polleninformation: async_setup_entry using coordinator: %s", coordinator
        )

    # Get existing entities from registry to handle stale data scenarios
    ent_reg = er.async_get(hass)
    existing_entities = er.async_entries_for_config_entry(ent_reg, entry.entry_id)
    existing_unique_ids = {
        e.unique_id
        for e in existing_entities
        if e.domain == "sensor" and not e.disabled
    }

    has_data = coordinator.data is not None
    contamination = coordinator.data.get("contamination", []) if has_data else []
    is_data_empty = len(contamination) == 0

    if DEBUG:
        _LOGGER.debug(
            "Polleninformation: has_data=%s, contamination_count=%s, existing_entities=%s",
            has_data,
            len(contamination),
            len(existing_unique_ids),
        )

    data = entry.data
    lat = data["latitude"]
    lon = data["longitude"]
    country = data["country"]
    lang = data.get("lang", DEFAULT_LANG)
    location_title = data.get("location_title")

    if not location_title or location_title.strip() == "":
        from .utils import async_get_country_options

        country_options = await async_get_country_options(hass)
        country_name = country_options.get(country, country)
        lat_str = f"{lat:.4f}" if lat is not None else "?"
        lon_str = f"{lon:.4f}" if lon is not None else "?"
        location_title = f"{country_name} ({lat_str}, {lon_str})"
    location_slug = normalize(location_title)

    language_block_current = await async_get_language_block(hass, lang)
    language_block_en = await async_get_language_block(hass, "en")
    levels_current = LEVELS.get(
        lang, LEVELS.get("en", ["none", "low", "moderate", "high", "very high"])
    )
    levels_en = LEVELS.get("en", ["none", "low", "moderate", "high", "very high"])

    entities: list[SensorEntity] = []
    new_unique_ids: set[str] = set()

    for item in contamination:
        poll_title_full = item.get("poll_title", "<unknown>")
        poll_title_local = capitalize_first(poll_title_full.split("(", 1)[0].strip())
        latin = None
        if "(" in poll_title_full and ")" in poll_title_full:
            latin = poll_title_full.split("(", 1)[1].split(")", 1)[0].strip()
        if not latin:
            for allergen in language_block_current.get("poll_titles", []):
                if allergen.get("name") == poll_title_local:
                    latin = allergen.get("latin")
                    break
        allergen_en_obj = (
            get_allergen_info_by_latin(latin, language_block_en) if latin else None
        )
        allergen_en = allergen_en_obj["name"] if allergen_en_obj else poll_title_local
        allergen_la = latin if latin else ""
        slug_en = slugify(allergen_en) if allergen_en else slugify(poll_title_local)
        icon = ALLERGEN_ICON_MAP.get(slug_en, ALLERGEN_ICON_MAP["default"])

        sensor = PolleninformationSensor(
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
        entities.append(sensor)
        if sensor.unique_id:
            new_unique_ids.add(sensor.unique_id)

    # Allergy risk daily sensor - only if contamination has data (otherwise allergyrisk is meaningless)
    allergyrisk = (
        coordinator.data.get("allergyrisk", {})
        if has_data and not is_data_empty
        else {}
    )
    if allergyrisk:
        sensor = AllergyRiskSensor(
            coordinator=coordinator,
            allergyrisk=allergyrisk,
            levels_current=levels_current,
            location_slug=location_slug,
            location_title=location_title,
        )
        entities.append(sensor)
        if sensor.unique_id:
            new_unique_ids.add(sensor.unique_id)

    # Allergy risk hourly sensor - only if contamination has data (otherwise allergyrisk is meaningless)
    allergyrisk_hourly = (
        coordinator.data.get("allergyrisk_hourly", {})
        if has_data and not is_data_empty
        else {}
    )
    if allergyrisk_hourly:
        sensor = AllergyRiskHourlySensor(
            coordinator=coordinator,
            allergyrisk_hourly=allergyrisk_hourly,
            levels_current=levels_current,
            location_slug=location_slug,
            location_title=location_title,
        )
        entities.append(sensor)
        if sensor.unique_id:
            new_unique_ids.add(sensor.unique_id)

    # Recreate stale entities from registry when API returns empty data
    stale_since = datetime.now().isoformat() if is_data_empty else None
    if is_data_empty and existing_unique_ids:
        _LOGGER.warning(
            "API returned empty data for %s, recreating %d entities as stale",
            location_title,
            len(existing_unique_ids),
        )
        for unique_id in existing_unique_ids:
            if unique_id in new_unique_ids:
                continue
            parts = unique_id.split("_", 2) if unique_id else []
            if len(parts) < 3:
                continue
            allergen_slug = parts[2]
            if allergen_slug == "allergy_risk":
                sensor = AllergyRiskSensor(
                    coordinator=coordinator,
                    allergyrisk={},
                    levels_current=levels_current,
                    location_slug=location_slug,
                    location_title=location_title,
                    is_stale=True,
                    stale_since=stale_since,
                )
            elif allergen_slug == "allergy_risk_hourly":
                sensor = AllergyRiskHourlySensor(
                    coordinator=coordinator,
                    allergyrisk_hourly={},
                    levels_current=levels_current,
                    location_slug=location_slug,
                    location_title=location_title,
                    is_stale=True,
                    stale_since=stale_since,
                )
            else:
                allergen_en = allergen_slug.replace("_", " ").title()
                icon = ALLERGEN_ICON_MAP.get(
                    allergen_slug, ALLERGEN_ICON_MAP["default"]
                )
                sensor = PolleninformationSensor(
                    coordinator=coordinator,
                    sensor_type="pollen",
                    allergen_name=allergen_en,
                    allergen_en=allergen_en,
                    allergen_slug=allergen_slug,
                    allergen_latin="",
                    levels_current=levels_current,
                    levels_en=levels_en,
                    location_slug=location_slug,
                    location_title=location_title,
                    icon=icon,
                    is_stale=True,
                    stale_since=stale_since,
                )
            entities.append(sensor)
            if sensor.unique_id:
                new_unique_ids.add(sensor.unique_id)

    async_add_entities(entities, update_before_add=True)


class PolleninformationSensor(CoordinatorEntity, SensorEntity):
    """Pollen allergen sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator,
        sensor_type: str,
        allergen_name: str,
        allergen_en: str,
        allergen_slug: str,
        allergen_latin: str,
        levels_current: list,
        levels_en: list,
        location_slug: str,
        location_title: str,
        icon: str,
        is_stale: bool = False,
        stale_since: str | None = None,
    ) -> None:
        super().__init__(coordinator)
        self.sensor_type = sensor_type
        self._allergen_name = allergen_name
        self._allergen_en = allergen_en
        self._allergen_slug = allergen_slug
        self._allergen_latin = allergen_latin
        self._levels_current = levels_current
        self._levels_en = levels_en
        self._location_slug = location_slug
        self._location_title = location_title
        self._is_stale = is_stale
        self._stale_since = stale_since

        self._attr_name = allergen_name
        self._attr_unique_id = f"polleninformation_{location_slug}_{allergen_slug}"
        self._attr_icon = icon
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{location_slug}")},
            "name": f"Polleninformation ({location_title})",
            "manufacturer": "Austrian Pollen Information Service",
        }
        if is_stale:
            self._attr_extra_state_attributes = {
                "data_stale": True,
                "stale_since": stale_since,
            }

    @property
    def suggested_object_id(self) -> str:
        return self._allergen_slug

    @property
    def available(self) -> bool:
        # Only unavailable if coordinator update failed (connectivity issue)
        # Stale/empty data still shows as available but with state "unknown"
        return self.coordinator.last_update_success is not False

    @property
    def native_value(self) -> str | None:
        if not self.coordinator.data:
            return None
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
            return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if not self.coordinator.data:
            attrs: dict[str, Any] = {}
            if self._is_stale:
                attrs["data_stale"] = True
                attrs["stale_since"] = self._stale_since
            return attrs

        contamination = self.coordinator.data.get("contamination", [])
        forecast = []
        base_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        for item in contamination:
            poll_title = item.get("poll_title", "").split("(", 1)[0].strip()
            if poll_title.lower() == self._allergen_name.lower():
                for day in range(1, 5):
                    val = item.get(f"contamination_{day}", 0)
                    level_name = (
                        self._levels_current[val]
                        if isinstance(val, int) and val < len(self._levels_current)
                        else str(val)
                    )
                    forecast.append(
                        {
                            "time": (base_date + timedelta(days=day - 1)).strftime(
                                "%Y-%m-%dT%H:%M:%S"
                            ),
                            "level": val,
                            "level_name": level_name,
                        }
                    )
                break

        today_raw = forecast[0] if forecast else None
        tomorrow_raw = forecast[1] if len(forecast) > 1 else None
        attrs = {
            "forecast": forecast,
            "numeric_state": today_raw["level"] if today_raw else None,
            "named_state": today_raw["level_name"] if today_raw else None,
            "tomorrow_numeric_state": tomorrow_raw["level"] if tomorrow_raw else None,
            "tomorrow_named_state": tomorrow_raw["level_name"]
            if tomorrow_raw
            else None,
            "friendly_name": self._allergen_name,
            "name_en": self._allergen_en,
            "name_la": self._allergen_latin,
            "allergen_slug": self._allergen_slug,
            "location_title": self._location_title,
            "location_slug": self._location_slug,
            "type": self.sensor_type,
            "attribution": "Austrian Pollen Information Service",
            "icon": self._attr_icon,
            "levels_current": self._levels_current,
            "levels_en": self._levels_en,
            "update_success": self.coordinator.data is not None,
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        if self._is_stale:
            attrs["data_stale"] = True
            attrs["stale_since"] = self._stale_since
        return attrs


class AllergyRiskSensor(CoordinatorEntity, SensorEntity):
    """Daily allergy risk sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator,
        allergyrisk: dict,
        levels_current: list,
        location_slug: str,
        location_title: str,
        is_stale: bool = False,
        stale_since: str | None = None,
    ) -> None:
        super().__init__(coordinator)
        self._allergyrisk = allergyrisk
        self._levels_current = levels_current
        self._location_slug = location_slug
        self._location_title = location_title
        self._is_stale = is_stale
        self._stale_since = stale_since

        self._attr_name = "Allergy risk"
        self._attr_unique_id = f"polleninformation_{location_slug}_allergy_risk"
        self._attr_icon = "mdi:alert"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{location_slug}")},
            "name": f"Polleninformation ({location_title})",
            "manufacturer": "Austrian Pollen Information Service",
        }
        if is_stale:
            self._attr_extra_state_attributes = {
                "data_stale": True,
                "stale_since": stale_since,
            }

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success is not False

    @property
    def native_value(self) -> str | None:
        if self._is_stale or not self._allergyrisk:
            return None
        value = self._allergyrisk.get("allergyrisk_1", None)
        scaled = scale_allergy_risk(value) if value is not None else None
        if scaled is not None and scaled < len(self._levels_current):
            return self._levels_current[scaled]
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if self._is_stale or not self._allergyrisk:
            attrs: dict[str, Any] = {
                "location_title": self._location_title,
                "location_slug": self._location_slug,
                "attribution": "Austrian Pollen Information Service",
            }
            if self._is_stale:
                attrs["data_stale"] = True
                attrs["stale_since"] = self._stale_since
            return attrs

        forecast = []
        base_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        for day in range(1, 5):
            value_raw = self._allergyrisk.get(f"allergyrisk_{day}", None)
            scaled = scale_allergy_risk(value_raw) if value_raw is not None else None
            level_name = (
                self._levels_current[scaled]
                if scaled is not None and scaled < len(self._levels_current)
                else None
            )
            forecast.append(
                {
                    "time": (base_date + timedelta(days=day - 1)).strftime(
                        "%Y-%m-%dT%H:%M:%S"
                    ),
                    "level": scaled,
                    "level_name": level_name,
                    "level_raw": value_raw,
                }
            )
        raw_value = self._allergyrisk.get("allergyrisk_1", None)
        scaled_today = scale_allergy_risk(raw_value) if raw_value is not None else None
        return {
            "named_state": self.native_value,
            "numeric_state": scaled_today,
            "numeric_state_raw": raw_value,
            "forecast": forecast,
            "location_title": self._location_title,
            "location_slug": self._location_slug,
            "attribution": "Austrian Pollen Information Service",
            "update_success": self.coordinator.data is not None,
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }


class AllergyRiskHourlySensor(CoordinatorEntity, SensorEntity):
    """Hourly allergy risk sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator,
        allergyrisk_hourly: dict,
        levels_current: list,
        location_slug: str,
        location_title: str,
        is_stale: bool = False,
        stale_since: str | None = None,
    ) -> None:
        super().__init__(coordinator)
        self._allergyrisk_hourly = allergyrisk_hourly
        self._levels_current = levels_current
        self._location_slug = location_slug
        self._location_title = location_title
        self._is_stale = is_stale
        self._stale_since = stale_since

        self._attr_name = "Allergy risk hourly"
        self._attr_unique_id = f"polleninformation_{location_slug}_allergy_risk_hourly"
        self._attr_icon = "mdi:timeline-clock"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{location_slug}")},
            "name": f"Polleninformation ({location_title})",
            "manufacturer": "Austrian Pollen Information Service",
        }
        if is_stale:
            self._attr_extra_state_attributes = {
                "data_stale": True,
                "stale_since": stale_since,
            }

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success is not False

    @property
    def native_value(self) -> str | None:
        if self._is_stale or not self._allergyrisk_hourly:
            return None
        now_hour = datetime.now().hour
        values = self._allergyrisk_hourly.get("allergyrisk_hourly_1", [])
        if 0 <= now_hour < len(values):
            raw = values[now_hour]
            scaled = scale_allergy_risk(raw)
            if scaled is not None and scaled < len(self._levels_current):
                return self._levels_current[scaled]
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if self._is_stale or not self._allergyrisk_hourly:
            attrs: dict[str, Any] = {
                "location_title": self._location_title,
                "location_slug": self._location_slug,
                "attribution": "Austrian Pollen Information Service",
            }
            if self._is_stale:
                attrs["data_stale"] = True
                attrs["stale_since"] = self._stale_since
            return attrs

        base_time = datetime.now(timezone.utc).replace(
            minute=0, second=0, microsecond=0
        )
        forecast = []
        for day in range(1, 5):
            values = self._allergyrisk_hourly.get(f"allergyrisk_hourly_{day}", [])
            for hour, raw in enumerate(values):
                dt = base_time + timedelta(days=day - 1, hours=hour)
                scaled = scale_allergy_risk(raw)
                named = (
                    self._levels_current[scaled]
                    if scaled is not None and scaled < len(self._levels_current)
                    else None
                )
                forecast.append(
                    {
                        "time": dt.isoformat(),
                        "level": scaled,
                        "level_name": named,
                        "level_raw": raw,
                    }
                )

        now_hour = datetime.now().hour
        values_today = self._allergyrisk_hourly.get("allergyrisk_hourly_1", [])
        raw_now = values_today[now_hour] if 0 <= now_hour < len(values_today) else None
        scaled_now = scale_allergy_risk(raw_now) if raw_now is not None else None
        named_now = (
            self._levels_current[scaled_now]
            if scaled_now is not None and scaled_now < len(self._levels_current)
            else None
        )
        return {
            "named_state": named_now,
            "numeric_state": scaled_now,
            "numeric_state_raw": raw_now,
            "forecast": forecast,
            "location_title": self._location_title,
            "location_slug": self._location_slug,
            "attribution": "Austrian Pollen Information Service",
            "update_success": self.coordinator.data is not None,
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
