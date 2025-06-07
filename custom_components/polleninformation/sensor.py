# custom_components/polleninformation/sensor.py
"""Sensorplattform för polleninformation.at."""

import os
import json
import logging
import aiohttp
import async_timeout
import re
from datetime import timedelta, datetime
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    CoordinatorEntity,
)

_LOGGER = logging.getLogger(__name__)

AVAILABLE_COUNTRIES_FILE = os.path.join(
    os.path.dirname(__file__), "available_countries.json"
)

POLLENAT_API_URL = (
    "https://www.polleninformation.at/index.php"
    "?eID=appinterface"
    "&pure_json=1"
    "&lang_code={lang}"
    "&lang_id=0"
    "&action=getFullContaminationData"
    "&type=gps"
    "&value[latitude]={lat}"
    "&value[longitude]={lon}"
    "&country_id={country_id}"
    "&personal_contamination=false"
    "&sensitivity=0"
    "&country={country}"
)

# Sluggifiering: använd samma robusta logik som test-scriptet
def slugify(text: str) -> str:
    # Ta bort allt efter eventuell parentes
    if "(" in text:
        text = text.split("(", 1)[0]
    text = text.strip().lower()
    # Ersätt svenska/tyska tecken (kan byggas ut)
    text = (
        text.replace("ö", "o")
        .replace("ä", "a")
        .replace("å", "a")
        .replace("ß", "ss")
        .replace("ü", "u")
        .replace("é", "e")
        .replace("è", "e")
        .replace("ç", "c")
        .replace("ı", "i")
        .replace("ğ", "g")
        .replace("ş", "s")
        .replace("ñ", "n")
        .replace("č", "c")
        .replace("ř", "r")
        .replace("ą", "a")
        .replace("ę", "e")
        .replace("ł", "l")
        .replace("ś", "s")
        .replace("ż", "z")
        .replace("ź", "z")
    )
    text = re.sub(r"[\s\-]+", "_", text)
    text = re.sub(r"[^a-z0-9_]", "", text)
    return text.strip("_")

def extract_place_slug(full_location: str) -> str:
    """
    Extrahera ort utan postnummer/kod. (t ex "9020 Klagenfurt" → "klagenfurt")
    """
    full_location = full_location.strip()
    parts = full_location.split(maxsplit=1)
    if len(parts) == 2 and re.match(r"^[A-Za-z0-9\-]+$", parts[0]):
        place_name = parts[1]
    else:
        place_name = full_location
    return slugify(place_name)

def load_available_countries():
    with open(AVAILABLE_COUNTRIES_FILE, encoding="utf-8") as f:
        data = json.load(f)
    return data["countries"]

def get_country_data(code):
    for country in load_available_countries():
        if country["code"] == code:
            return country
    raise ValueError(f"Country code '{code}' not found in available_countries.json")

async def fetch_pollen_data(lat, lon, country, country_id, lang="en"):
    url = POLLENAT_API_URL.format(
        lat=lat, lon=lon, country=country, country_id=country_id, lang=lang
    )
    _LOGGER.debug(f"Fetching pollen info: {url}")
    try:
        async with async_timeout.timeout(10):
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    resp.raise_for_status()
                    payload = await resp.json()
                    return payload.get("result", {})
    except Exception as e:
        _LOGGER.error(f"API error: {e}")
        return {}

# ---- Sensorplattform ----
async def async_setup_entry(hass, config_entry, async_add_entities):
    await _setup_sensors(
        hass,
        async_add_entities,
        config_entry.data.get("country", "SE"),
        config_entry.data.get("latitude", hass.config.latitude),
        config_entry.data.get("longitude", hass.config.longitude),
        config_entry.data.get("lang", "en"),
    )

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    await _setup_sensors(
        hass,
        async_add_entities,
        config.get("country", "SE"),
        config.get("lat", hass.config.latitude),
        config.get("lon", hass.config.longitude),
        config.get("lang", "en"),
    )

async def _setup_sensors(hass, async_add_entities, country_code, lat, lon, lang):
    country_data = get_country_data(country_code)
    country_id = country_data["country_id"][0]

    coordinator = PollenDataCoordinator(
        hass, lat, lon, country_code, country_id, lang
    )
    await coordinator.async_config_entry_first_refresh()

    result = coordinator.data
    if not result or "contamination" not in result:
        _LOGGER.warning("No pollen data returned for initial setup.")
        return

    place = result.get("locationtitle") or country_code
    place_slug = extract_place_slug(place)
    allergens = result["contamination"]

    entities = []
    for poll in allergens:
        allergen_en = poll.get("poll_title_en") or poll.get("poll_title")
        allergen_slug = slugify(allergen_en)
        entity_id = f"polleninformation_{place_slug}_{allergen_slug}"
        sensor = PolleninformationAllergenSensor(
            coordinator=coordinator,
            entity_id=entity_id,
            friendly_place=place,
            place_slug=place_slug,
            allergen_en=allergen_en,
            allergen_slug=allergen_slug,
            poll=poll,
        )
        entities.append(sensor)

    async_add_entities(entities, True)

class PollenDataCoordinator(DataUpdateCoordinator):
    """Hämtar pollen-data var 6:e timme och cachar resultat."""

    def __init__(self, hass, lat, lon, country, country_id, lang):
        super().__init__(
            hass,
            _LOGGER,
            name="Polleninformation",
            update_interval=timedelta(hours=6),
        )
        self.lat = lat
        self.lon = lon
        self.country = country
        self.country_id = country_id
        self.lang = lang

    async def _async_update_data(self):
        return await fetch_pollen_data(
            self.lat, self.lon, self.country, self.country_id, self.lang
        )

class PolleninformationAllergenSensor(CoordinatorEntity, SensorEntity):
    """En sensor per allergen."""

    def __init__(self, coordinator, entity_id, friendly_place, place_slug, allergen_en, allergen_slug, poll):
        super().__init__(coordinator)
        self._attr_unique_id = entity_id
        self._attr_name = f"Polleninformation {friendly_place}: {allergen_en}"
        self._poll_title = allergen_en
        self._poll_slug = allergen_slug
        self._place_slug = place_slug
        self._friendly_place = friendly_place

    @property
    def unique_id(self):
        return self._attr_unique_id

    @property
    def name(self):
        return self._attr_name

    @property
    def native_value(self):
        # Returnera dagens kontaminationsnivå (contamination_1)
        data = self.coordinator.data
        if not data or "contamination" not in data:
            return None
        for poll in data["contamination"]:
            allergen_en = poll.get("poll_title_en") or poll.get("poll_title")
            if slugify(allergen_en) == self._poll_slug:
                return poll.get("contamination_1")
        return None

    @property
    def extra_state_attributes(self):
        # Skapa alla önskade attribut enligt dina exempel.
        data = self.coordinator.data
        today = None
        tomorrow = None
        forecast_list = []
        update_success = bool(data and "contamination" in data)
        last_updated = datetime.now().strftime("%-d %B %Y kl. %H:%M:%S")

        # Hitta rätt allergen
        poll_obj = None
        if data and "contamination" in data:
            for poll in data["contamination"]:
                allergen_en = poll.get("poll_title_en") or poll.get("poll_title")
                if slugify(allergen_en) == self._poll_slug:
                    poll_obj = poll
                    break

        if poll_obj:
            # Bygg forecast
            for i in range(1, 8):
                day_key = f"contamination_{i}"
                date_key = f"date_{i}"
                level = poll_obj.get(day_key)
                # Hämta nivå-namn
                level_name = get_level_name(level)
                forecast_list.append({
                    "time": poll_obj.get(date_key),
                    "level_name": level_name,
                    "level": level,
                })
            # Today och tomorrow
            today = {
                "time": poll_obj.get("date_1"),
                "level_name": get_level_name(poll_obj.get("contamination_1")),
                "level": poll_obj.get("contamination_1"),
            }
            tomorrow = {
                "time": poll_obj.get("date_2"),
                "level_name": get_level_name(poll_obj.get("contamination_2")),
                "level": poll_obj.get("contamination_2"),
            }
        else:
            today = tomorrow = {}

        return {
            "place_slug": self._place_slug,
            "allergen_slug": self._poll_slug,
            "allergen": self._poll_title,
            "forecast": forecast_list,
            "raw": today,
            "numeric_state": today.get("level") if today else None,
            "named_state": today.get("level_name") if today else None,
            "tomorrow_raw": tomorrow,
            "tomorrow_numeric_state": tomorrow.get("level") if tomorrow else None,
            "tomorrow_named_state": tomorrow.get("level_name") if tomorrow else None,
            "update_success": update_success,
            "last_updated": last_updated,
        }

def get_level_name(level):
    try:
        level = int(level)
    except Exception:
        return "Okänd"
    # Sätt nivå-namn (anpassa om nivålistan ändras)
    names = [
        "Inga halter",
        "Låga halter",
        "Måttliga halter",
        "Höga halter",
        "Mycket höga halter",
    ]
    if 0 <= level < len(names):
        return names[level]
    return "Okänd"
