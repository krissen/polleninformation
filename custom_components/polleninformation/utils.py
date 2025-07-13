""" custom_components/polleninformation/utils.py """
import re
import unicodedata
import json
import os

LANGUAGE_MAP_FILE = os.path.join(os.path.dirname(__file__), "language_map.json")

def _sync_load_language_map():
    with open(LANGUAGE_MAP_FILE, encoding="utf-8") as f:
        return json.load(f)

async def async_load_language_map(hass):
    return await hass.async_add_executor_job(_sync_load_language_map)

def load_available_languages_sync():
    data = _sync_load_language_map()
    out = []
    for k, v in data.items():
        if isinstance(v, dict) and "lang_code" in v and "lang" in v:
            out.append({
                "key": k,
                "lang_code": v["lang_code"],
                "lang": v["lang"],
            })
    return out

async def async_load_available_languages(hass):
    data = await async_load_language_map(hass)
    out = []
    for k, v in data.items():
        if isinstance(v, dict) and "lang_code" in v and "lang" in v:
            out.append({
                "key": k,
                "lang_code": v["lang_code"],
                "lang": v["lang"],
            })
    return out

def get_language_options_sync():
    langs = load_available_languages_sync()
    return {l["key"]: l["lang"] for l in langs}

async def async_get_language_options(hass):
    langs = await async_load_available_languages(hass)
    return {l["key"]: l["lang"] for l in langs}

def get_lang_info_by_code_sync(lang_code):
    langs = load_available_languages_sync()
    for l in langs:
        if l["lang_code"] == lang_code:
            return l
    return None

async def async_get_lang_info_by_code(hass, lang_code):
    langs = await async_load_available_languages(hass)
    for l in langs:
        if l["lang_code"] == lang_code:
            return l
    return None

def find_best_lang_key_for_locale_sync(locale_tag):
    langs = load_available_languages_sync()
    for l in langs:
        if l["lang_code"] == locale_tag:
            return l["key"]
    short = locale_tag[:2].lower()
    for l in langs:
        if l["lang_code"] == short:
            return l["key"]
    for l in langs:
        if l["lang_code"] == "en":
            return l["key"]
    return langs[0]["key"] if langs else "1"

async def async_find_best_lang_key_for_locale(hass, locale_tag):
    langs = await async_load_available_languages(hass)
    for l in langs:
        if l["lang_code"] == locale_tag:
            return l["key"]
    short = locale_tag[:2].lower()
    for l in langs:
        if l["lang_code"] == short:
            return l["key"]
    for l in langs:
        if l["lang_code"] == "en":
            return l["key"]
    return langs[0]["key"] if langs else "1"

def slugify(text: str) -> str:
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
    full_location = full_location.strip()
    parts = full_location.split(maxsplit=1)
    if parts and re.match(r"^[A-Za-z0-9\-]+$", parts[0]) and len(parts) == 2:
        place_name = parts[1]
    else:
        place_name = full_location
    return slugify(place_name)

def split_location(locationtitle):
    locationtitle = locationtitle.strip()
    parts = locationtitle.split(maxsplit=1)
    if parts and re.match(r"^[A-Za-z0-9\-]+$", parts[0]) and len(parts) == 2:
        return parts[0], parts[1]
    return "", locationtitle

def get_language_block_sync(L):
    data = _sync_load_language_map()
    return data.get(str(L), {})

async def async_get_language_block(hass, L):
    data = await async_load_language_map(hass)
    return data.get(str(L), {})

def get_allergen_info_by_latin(latin, language_block):
    for allergen in language_block.get("poll_titles", []):
        if allergen.get("latin") == latin:
            return allergen
    return None
