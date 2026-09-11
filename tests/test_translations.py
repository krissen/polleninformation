"""Tests for translation and language-map completeness."""

import json
from pathlib import Path

from custom_components.polleninformation.const import SUPPORTED_LANGUAGES

REPO_ROOT = Path(__file__).resolve().parent.parent
TRANSLATIONS_DIR = REPO_ROOT / "custom_components" / "polleninformation" / "translations"
LANGUAGE_MAP_FILE = REPO_ROOT / "custom_components" / "polleninformation" / "language_map.json"


def _flatten_keys(data: dict, prefix: str = "") -> set[str]:
    """Return the set of dotted leaf-key paths in a nested translations dict."""
    keys = set()
    for key, value in data.items():
        path = f"{prefix}{key}"
        if isinstance(value, dict):
            keys |= _flatten_keys(value, prefix=f"{path}/")
        else:
            keys.add(path)
    return keys


def _load_translation(lang: str) -> dict:
    path = TRANSLATIONS_DIR / f"{lang}.json"
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def test_all_languages_have_translation_files():
    """Every supported language ships a translations/<lang>.json file."""
    for lang in SUPPORTED_LANGUAGES:
        assert (TRANSLATIONS_DIR / f"{lang}.json").is_file(), f"Missing translations/{lang}.json"


def test_translation_keys_match_english():
    """Every language's key set matches en.json's -- no missing, no extra keys.

    A language file added without keeping pace with en.json either falls
    back to English silently (missing keys) or carries dead keys that no
    longer mean anything (extra keys). Both drift unnoticed until read.
    """
    english_keys = _flatten_keys(_load_translation("en"))
    for lang in SUPPORTED_LANGUAGES:
        if lang == "en":
            continue
        keys = _flatten_keys(_load_translation(lang))
        missing = english_keys - keys
        extra = keys - english_keys
        assert not missing, f"{lang}.json is missing keys: {sorted(missing)}"
        assert not extra, f"{lang}.json has extra keys not in en.json: {sorted(extra)}"


def test_language_map_covers_all_languages():
    """Every supported language has an entry in language_map.json."""
    with LANGUAGE_MAP_FILE.open(encoding="utf-8") as f:
        language_map = json.load(f)
    for lang in SUPPORTED_LANGUAGES:
        assert lang in language_map, f"Missing {lang} entry in language_map.json"


def test_language_map_poll_ids_match_english():
    """Every language's poll_id set matches the English set.

    An allergen added for one language without the others leaves those
    languages unable to name a pollen the API still reports for them --
    the sensor falls back to a raw poll_id instead of a translated name.
    """
    with LANGUAGE_MAP_FILE.open(encoding="utf-8") as f:
        language_map = json.load(f)
    english_ids = {entry["poll_id"] for entry in language_map["en"]["poll_titles"]}
    for lang in SUPPORTED_LANGUAGES:
        if lang == "en":
            continue
        ids = {entry["poll_id"] for entry in language_map[lang]["poll_titles"]}
        missing = english_ids - ids
        extra = ids - english_ids
        assert not missing, f"{lang} language_map is missing poll_id(s): {sorted(missing)}"
        assert not extra, f"{lang} language_map has extra poll_id(s): {sorted(extra)}"
