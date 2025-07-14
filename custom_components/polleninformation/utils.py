""" custom_components/polleninformation/utils.py """

import json
import os
import re
import unicodedata

import aiohttp

from .const import (COUNTRY_DISPLAY_NAMES, LANGUAGE_DISPLAY_NAMES,
                    SUPPORTED_COUNTRIES, SUPPORTED_LANGUAGES)

LANGUAGE_MAP_FILE = os.path.join(os.path.dirname(__file__), "language_map.json")



async def async_get_country_code_from_latlon(hass, lat, lon):
    """
    Get ISO 3166-1 alpha-2 country code from latitude/longitude using Nominatim API (OpenStreetMap).
    Returns country code in upper case, e.g. 'SE' for Sweden, or None if not found.
    """
    url = "https://nominatim.openstreetmap.org/reverse"
    params = {
        "lat": lat,
        "lon": lon,
        "format": "json",
        "zoom": 3,
        "addressdetails": 1,
    }
    headers = {"User-Agent": "Home Assistant Polleninformation Integration"}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, headers=headers, timeout=5) as resp:
            if resp.status == 200:
                result = await resp.json()
                return result.get("address", {}).get("country_code", "").upper()
    return None

async def async_load_available_languages(hass):
    """
    Return a list of available language blocks from language_map.json.
    Each block is a dict with keys like 'lang_code', 'lang', etc.
    """
    data = await async_load_language_map(hass)
    # Return only dicts with 'lang_code' and 'lang'
    return [
        v
        for v in data.values()
        if isinstance(v, dict) and "lang_code" in v and "lang" in v
    ]


def _sync_load_language_map():
    """Load language map synchronously from local JSON file."""
    with open(LANGUAGE_MAP_FILE, encoding="utf-8") as f:
        return json.load(f)


def get_country_code_map(hass=None):
    """
    Return a mapping from country display names to ISO country codes.

    Uses static mapping, but can be extended to fetch from Home Assistant or integration settings if needed.
    Keys are display names (as shown in UI), values are ISO codes (as used by API).

    Example:
        {
            "Sweden": "SE",
            "Norway": "NO",
            "Ukraine": "UA",
            "Austria": "AT",
            ...
        }
    """
    # You may want to extend this mapping if new countries are supported.
    return {
        "Austria": "AT",
        "Sweden": "SE",
        "Norway": "NO",
        "Ukraine": "UA",
        "Germany": "DE",
        "Poland": "PL",
        "Switzerland": "CH",
        "Czech Republic": "CZ",
        "Slovakia": "SK",
        "Slovenia": "SI",
        "Hungary": "HU",
        "Croatia": "HR",
        "Italy": "IT",
        "France": "FR",
        "Spain": "ES",
        "Belgium": "BE",
        "Netherlands": "NL",
        "Denmark": "DK",
        "Finland": "FI",
        "Estonia": "EE",
        "Latvia": "LV",
        "Lithuania": "LT",
        "Romania": "RO",
        "Bulgaria": "BG",
        "Greece": "GR",
        "Ireland": "IE",
        "United Kingdom": "GB",
        "Portugal": "PT",
        # Add more as needed
    }


async def async_load_language_map(hass):
    """Load language map asynchronously."""
    return await hass.async_add_executor_job(_sync_load_language_map)


# --- LANGUAGE HANDLING ---


def get_language_options_sync():
    """
    Return dict of ISO 639-1 language code -> display name.
    Always uses SUPPORTED_LANGUAGES and LANGUAGE_DISPLAY_NAMES from const.py.
    """
    return {
        code: LANGUAGE_DISPLAY_NAMES.get(code, code) for code in SUPPORTED_LANGUAGES
    }


async def async_get_language_options(hass):
    """
    Return dict of ISO 639-1 language code -> display name, async.
    Always uses SUPPORTED_LANGUAGES and LANGUAGE_DISPLAY_NAMES from const.py.
    """
    return get_language_options_sync()


def get_lang_info_by_code_sync(lang_code):
    """
    Return info dict for language code from language_map.json, or None if not found.
    """
    data = _sync_load_language_map()
    for k, v in data.items():
        if isinstance(v, dict) and v.get("lang_code") == lang_code:
            return v
    return None


async def async_get_lang_info_by_code(hass, lang_code):
    """
    Return info dict for language code from language_map.json, async.
    """
    data = await async_load_language_map(hass)
    for k, v in data.items():
        if isinstance(v, dict) and v.get("lang_code") == lang_code:
            return v
    return None


def find_best_lang_code_for_locale_sync(locale_tag):
    """
    Find best matching ISO 639-1 language code for a given locale.
    Returns the two-letter code, fallback to 'en' if no match.
    """
    locale_tag = str(locale_tag).lower()
    if locale_tag in SUPPORTED_LANGUAGES:
        return locale_tag
    short = locale_tag[:2]
    if short in SUPPORTED_LANGUAGES:
        return short
    return "en"


async def async_find_best_lang_code_for_locale(hass, locale_tag):
    """
    Async version of find_best_lang_code_for_locale_sync.
    """
    return find_best_lang_code_for_locale_sync(locale_tag)


# --- COUNTRY HANDLING ---


def get_country_options_sync():
    """
    Return dict of ISO 3166-1 alpha-2 country code -> display name.
    Uses SUPPORTED_COUNTRIES and COUNTRY_DISPLAY_NAMES from const.py.
    """
    return {code: COUNTRY_DISPLAY_NAMES.get(code, code) for code in SUPPORTED_COUNTRIES}


async def async_get_country_options(hass):
    """
    Return dict of ISO 3166-1 alpha-2 country code -> display name, async.
    Uses SUPPORTED_COUNTRIES and COUNTRY_DISPLAY_NAMES from const.py.
    """
    return get_country_options_sync()


# --- MISC UTILS ---


def slugify(text: str) -> str:
    """
    Slugify a string for use in entity or object_id.
    """
    try:
        from unidecode import unidecode

        text = unidecode(text)
    except ImportError:
        text = (
            unicodedata.normalize("NFKD", text)
            .encode("ascii", "ignore")
            .decode("ascii")
        )

    text = text.split("(", 1)[0] if "(" in text else text
    text = text.strip().lower()
    text = (
        text.replace("ö", "o")
        .replace("ä", "a")
        .replace("å", "a")
        .replace("ß", "ss")
        .replace("'", "")
    )
    text = re.sub(r"[^\w]+", "_", text)
    text = text.strip("_")
    return text


def extract_place_slug(full_location: str) -> str:
    """
    Extract slug for a place from a full location string.
    """
    full_location = full_location.strip()
    parts = full_location.split(maxsplit=1)
    if parts and re.match(r"^[A-Za-z0-9\-]+$", parts[0]) and len(parts) == 2:
        place_name = parts[1]
    else:
        place_name = full_location
    return slugify(place_name)


def split_location(locationtitle):
    """
    Split location string into zip and name. Returns tuple (zip, place).
    """
    locationtitle = locationtitle.strip()
    parts = locationtitle.split(maxsplit=1)
    if parts and re.match(r"^[A-Za-z0-9\-]+$", parts[0]) and len(parts) == 2:
        return parts[0], parts[1]
    return "", locationtitle


def get_language_block_sync(lang_code):
    """
    Get language block for a given ISO code from language_map.json.
    """
    data = _sync_load_language_map()
    for k, v in data.items():
        if isinstance(v, dict) and v.get("lang_code") == lang_code:
            return v
    return {}


async def async_get_language_block(hass, lang_code):
    """
    Async version to get language block for ISO code.
    """
    data = await async_load_language_map(hass)
    for k, v in data.items():
        if isinstance(v, dict) and v.get("lang_code") == lang_code:
            return v
    return {}


def get_allergen_info_by_latin(latin, language_block):
    """
    Get allergen info from a language block by latin name.
    """
    for allergen in language_block.get("poll_titles", []):
        if allergen.get("latin") == latin:
            return allergen
    return None
