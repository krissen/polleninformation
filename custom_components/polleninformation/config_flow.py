# custom_components/polleninformation/sensor.py
"""Sensorplattform för polleninformation.at."""

import os
import json
import logging
import aiohttp
import async_timeout
import asyncio
import re
from datetime import timedelta

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

# Slugifierare: a-z0-9 och "_"
def slugify(text):
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s\-]+", "_", text)
    return text.strip("_")

async def async_load_available_countries(hass):
    """Läs available_countries.json asynkront via executor."""
    def _load_sync():
        with open(AVAILABLE_COUNTRIES_FILE, encoding="utf-8") as f:
            return json.load(f)["countries"]
    return await hass.async_add_executor_job(_load_sync)

async def async_get_country_data(hass, code):
    countries = await async_load_available_countries(hass)
    for country in countries:
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

def extract_place_slug(full_location: str) -> str:
    """Sluggifiera ortsnamnet, ta bort postnummer om först."""
    full_location = full_location.strip()
    parts = full_location.split(maxsplit=1)
    if len(parts) == 2 and re.match(r"^[A-Za-z0-9\-]+$", parts[0]):
        place_name = parts[1]
    else:
        place_name = full_location
    return slugify(place_name)

async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up polleninformation sensors."""
    country_code = config.get("country", "SE")
    lat = config.get("latitude", hass.config.latitude)
    lon = config.get("longitude", hass.config.longitude)
    lang = config.get("lang", "en")

    country_data = await async_get_country_data(hass, country_code)
    country_id = country_data["country_id"][0]

    # Coordinator: uppdaterar alla 6h
    coordinator = PollenDataCoordinator(
        hass, lat, lon, country_code, country_id, lang
    )
    await coordinator.async_config_entry_first_refresh()

    # Första hämtning för att få plats/allergener
    result = coordinator.data
    if not result or "contamination" not in result:
        _LOGGER.warning("No pollen data returned for initial setup.")
        return

    place = result.get("locationtitle", country_code)
    place_slug = extract_place_slug(place)
    allergens = result["contamination"]

    # Skapa en sensor per allergen
    entities = []
    for poll in allergens:
        allergen_en = poll.get("poll_title_en") or poll.get("poll_title")
        allergen_slug = slugify(allergen_en)
        entity_id = f"polleninformation_{place_slug}_{allergen_slug}"
        sensor = PolleninformationAllergenSensor(
            coordinator,
            entity_id=entity_id,
            friendly_place=place,
            allergen_en=allergen_en,
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

    def __init__(self, coordinator, entity_id, friendly_place, allergen_en, poll):
        super().__init__(coordinator)
        self._attr_unique_id = entity_id
        self._attr_name = f"Polleninformation {friendly_place}: {allergen_en}"
        self._poll_title = allergen_en
        self._poll_slug = slugify(allergen_en)
        self._place_slug = extract_place_slug(friendly_place)

    @property
    def unique_id(self):
        return self._attr_unique_id

    @property
    def name(self):
        return self._attr_name

    @property
    def native_value(self):
        # Hämtar nuvarande kontaminationsnivå (id: 1 = idag)
        data = self.coordinator.data
        if not data or "contamination" not in data:
            return None
        for poll in data["contamination"]:
            poll_en = poll.get("poll_title_en") or poll.get("poll_title")
            if slugify(poll_en) == self._poll_slug:
                return poll.get("contamination_1")
        return None

    @property
    def extra_state_attributes(self):
        # Lägg till mer info om allergen eller plats om du vill
        return {
            "place_slug": self._place_slug,
            "allergen_slug": self._poll_slug,
            "allergen": self._poll_title,
        }

