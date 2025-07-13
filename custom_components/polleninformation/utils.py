""" custom_components/polleninformation/utils.py """
import re
import unicodedata
import json
import os

LANGUAGE_MAP_FILE = os.path.join(os.path.dirname(__file__), "language_map.json")

def load_available_languages():
    try:
        with open(LANGUAGE_MAP_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []

    # Giltiga språk har både lang_code och lang
    out = []
    for k, v in data.items():
        if isinstance(v, dict) and "lang_code" in v and "lang" in v:
            out.append({
                "key": k,           # blocknyckel, används som L
                "lang_code": v["lang_code"],
                "lang": v["lang"],  # visningsnamn
            })
    return out

def get_language_options():
    # Returnerar dict för voluptuous: {blocknyckel: visningsnamn}
    langs = load_available_languages()
    return {l["key"]: l["lang"] for l in langs}

def get_lang_info_by_code(lang_code):
    langs = load_available_languages()
    for l in langs:
        if l["lang_code"] == lang_code:
            return l
    return None

def find_best_lang_key_for_locale(locale_tag):
    # locale_tag = "sv", "sv-SE", "en", "en-US", etc
    langs = load_available_languages()
    # Försök exakt match på lang_code
    for l in langs:
        if l["lang_code"] == locale_tag:
            return l["key"]
    # Försök match på första två bokstäver
    short = locale_tag[:2].lower()
    for l in langs:
        if l["lang_code"] == short:
            return l["key"]
    # Fallback: "1" (engelska), annars första i listan
    for l in langs:
        if l["lang_code"] == "en":
            return l["key"]
    return langs[0]["key"] if langs else "1"

def slugify(text: str) -> str:
    """Konverterar text till slug: gemener, ASCII, inga parenteser, endast a-z0-9_."""
    try:
        from unidecode import unidecode
        text = unidecode(text)
    except ImportError:
        text = (
            unicodedata.normalize("NFKD", text)
            .encode("ascii", "ignore")
            .decode("ascii")
        )

    # Ta bort parentesinnehåll
    text = text.split("(", 1)[0] if "(" in text else text
    text = text.strip().lower()

    # Ersätt diakrit-variationer och specialfall
    text = (
        text.replace("ö", "o")
        .replace("ä", "a")
        .replace("å", "a")
        .replace("ß", "ss")
        .replace("'", "")   # Tar bort apostrofer från translit
    )

    # Ersätt alla icke-alfanumeriska tecken med _
    text = re.sub(r"[^\w]+", "_", text)

    # Ta bort inledande och avslutande _
    text = text.strip("_")

    return text

def extract_place_slug(full_location: str) -> str:
    """Returnerar slugifierat platsnamn utan ev. postnummer/kod före första mellanslag."""
    full_location = full_location.strip()
    parts = full_location.split(maxsplit=1)
    if parts and re.match(r"^[A-Za-z0-9\-]+$", parts[0]) and len(parts) == 2:
        place_name = parts[1]
    else:
        place_name = full_location
    return slugify(place_name)

def split_location(locationtitle):
    """Dela locationtitle till (postnummer/kod, namn) – annars ('', locationtitle)."""
    locationtitle = locationtitle.strip()
    parts = locationtitle.split(maxsplit=1)
    if parts and re.match(r"^[A-Za-z0-9\-]+$", parts[0]) and len(parts) == 2:
        return parts[0], parts[1]
    return "", locationtitle

def load_language_map():
    try:
        with open(LANGUAGE_MAP_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def get_language_block(L):
    data = load_language_map()
    # L kan vara int eller str
    return data.get(str(L), {})

def get_allergen_info_by_latin(latin, language_block):
    for allergen in language_block.get("poll_titles", []):
        if allergen.get("latin") == latin:
            return allergen
    return None
