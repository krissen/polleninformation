"""Generate custom_components/polleninformation/language_map.json.

Two modes, both run from the repository root:

    python scripts/generate_language_codes.py           # fetch missing languages
    python scripts/generate_language_codes.py --repair  # revalidate, offline

The fetch mode asks the API for one forecast per interface language and
records the localized allergen names it answers with. It needs API_KEY (from
the environment or from .env) and network access, and it only fetches
languages the file does not already have.

The repair mode needs neither. It revalidates every latin name already in the
file with the same rules the fetch mode applies to a fresh response, which is
what lets an entry recorded before those rules existed correct itself. Run it
after changing the validation, and review the diff.

Both modes take their authority from LATIN_TO_ENGLISH_NAME in sensor.py, so
this script imports the integration and therefore needs Home Assistant
installed (the test venv has it).
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from custom_components.polleninformation.sensor import (
    LATIN_TO_ENGLISH_NAME,
    english_name_for_display_name,
    english_name_for_latin,
)

# ================================
# CONFIGURATION
# ================================

LAT = 48.2081743
LON = 16.3738189
COUNTRY = "AT"
LANG_CODES = [
    "de",
    "en",
    "fi",
    "sv",
    "fr",
    "it",
    "lv",
    "lt",
    "pl",
    "pt",
    "ru",
    "sk",
    "es",
    "tr",
    "uk",
    "hu",
]
DB_FILE = "custom_components/polleninformation/language_map.json"
DELAY_SEC = 2  # Polite delay between requests (adjust if needed)
HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "User-Agent": "Mozilla/5.0 (compatible; polleninfo-script/1.0)",
}

# The reverse of LATIN_TO_ENGLISH_NAME. The English names are unique, so this
# is lossless. It is the last resort for an entry whose display name is the
# English allergen name rather than a localized one, which is what the API
# sends for ragweed in some languages.
ENGLISH_NAME_TO_LATIN = {
    name.lower(): latin for latin, name in LATIN_TO_ENGLISH_NAME.items()
}


def load_db():
    """Load the existing language_map.json, or return empty dict."""
    if not os.path.exists(DB_FILE):
        return {}
    with open(DB_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_db(db):
    """Save the language_map.json file (pretty-printed, UTF-8)."""
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)
        # The file is checked in, so it ends with a newline like every other
        # source file. Without this every save shows up as a diff on the last
        # line.
        f.write("\n")


def get_language_name(lang_code):
    """Return the language name in English for a given ISO code."""
    # Minimal mapping; extend as needed.
    names = {
        "de": "German",
        "en": "English",
        "fi": "Finnish",
        "sv": "Swedish",
        "fr": "French",
        "it": "Italian",
        "lv": "Latvian",
        "lt": "Lithuanian",
        "pl": "Polish",
        "pt": "Portuguese",
        "ru": "Russian",
        "sk": "Slovak",
        "es": "Spanish",
        "tr": "Turkish",
        "uk": "Ukrainian",
        "hu": "Hungarian",
    }
    return names.get(lang_code, lang_code)


def split_poll_title(poll_title):
    """Split a poll_title into its display name and its bracketed latin name.

    This is the transcription step only: whatever the API put between the
    brackets comes back as the latin name, and a title without brackets comes
    back with none. resolve_latin decides what that is worth.
    """
    poll_title = poll_title or ""
    if "(" in poll_title and ")" in poll_title:
        name = poll_title.split("(", 1)[0].strip()
        latin = poll_title.split("(", 1)[1].split(")", 1)[0].strip()
    else:
        name = poll_title.strip()
        latin = ""
    return name, latin


# Everything a scientific name is allowed to be made of. The nomenclature
# codes require a name to be written in Latin letters, so a name never carries
# a diacritic or a non-Latin script; the multiplication sign is the one
# exception, since it marks a hybrid ("Ambrosia x helenae" is also written
# with it).
SCIENTIFIC_NAME_CHARACTERS = set(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ .-'×"
)


def could_be_a_scientific_name(latin):
    """Return whether a string could be a scientific name at all.

    This does not say the name exists, only that nothing rules it out. A
    string carrying a diacritic or a non-Latin script cannot be one, which is
    how a localized word the API put between the brackets is told apart from
    a genuine latin name the static map happens not to know.
    """
    return bool(latin) and set(latin) <= SCIENTIFIC_NAME_CHARACTERS


def resolve_latin(name, latin):
    """Return the latin name to record for an entry, plus any warnings.

    The API does not always put a latin name between the brackets, and does
    not always use brackets at all, so a transcribed latin name is checked
    against LATIN_TO_ENGLISH_NAME before it is trusted. When it fails, the
    display name is the second chance: it is either a latin name itself, the
    shape reported in issue #71, or the English allergen name, which is what
    the API sends for ragweed in some languages.

    A latin name the API did send is authoritative even when nothing resolves
    it, exactly as it is for the sensors: "Artemisia (Asteraceae)" is the
    composite family, not mugwort, and reading its display name as a latin
    name would record it as a different allergen. So the display name is only
    read as a latin name when the API sent none, and it is only read as an
    English allergen name when the API sent none or sent something that could
    not be a scientific name whatever it names.

    An entry no lookup recognizes is warned about and recorded exactly as the
    API sent it. Dropping it would hide a genuinely new allergen, which is the
    one case where this file has something to tell us.
    """
    if latin and english_name_for_latin(latin):
        return latin, []

    sent = f"latin name {latin!r}" if latin else "no latin name"

    if not latin and (english := english_name_for_display_name(name)):
        canonical = ENGLISH_NAME_TO_LATIN[english]
        warning = (
            f"{name!r}: the API sent {sent} and a display name that is one; "
            f"recording {canonical!r}"
        )
        return canonical, [warning]

    if not could_be_a_scientific_name(latin) and (
        canonical := ENGLISH_NAME_TO_LATIN.get(name.strip().lower())
    ):
        warning = (
            f"{name!r}: the API sent {sent} and an untranslated English "
            f"display name; recording {canonical!r}"
        )
        return canonical, [warning]

    if latin:
        warning = (
            f"{name!r}: the API sent {sent}, which no map knows. Keeping it: "
            f"a latin name the API sent identifies the allergen even when "
            f"nothing resolves it. If this is a new allergen it needs adding "
            f"to LATIN_TO_ENGLISH_NAME in sensor.py; please open an issue."
        )
    else:
        warning = (
            f"{name!r}: the API sent {sent} and a display name no map knows. "
            f"Recording it as sent. If this is a new allergen it needs adding "
            f"to LATIN_TO_ENGLISH_NAME in sensor.py; please open an issue."
        )
    return latin, [warning]


def poll_titles_from_contamination(contamination):
    """Return the poll_titles entries for a contamination block, plus warnings.

    Every entry in the block produces exactly one entry here, whether or not
    its allergen is recognized.
    """
    poll_titles = []
    warnings = []
    for poll in contamination:
        name, latin = split_poll_title(poll.get("poll_title", ""))
        latin, entry_warnings = resolve_latin(name, latin)
        warnings.extend(entry_warnings)
        poll_titles.append(
            {"name": name, "latin": latin, "poll_id": poll.get("poll_id")}
        )
    return poll_titles, warnings


def repair_db(db):
    """Revalidate every latin name already in the db, in place.

    Returns (changes, warnings), where a change is one corrected latin name.
    Entries are only ever rewritten, never removed: an allergen no map knows
    keeps what the API sent and is warned about again.
    """
    changes = []
    warnings = []
    for lang_code, entry in db.items():
        for poll in entry.get("poll_titles", []):
            name = poll.get("name", "")
            latin = poll.get("latin", "")
            resolved, entry_warnings = resolve_latin(name, latin)
            warnings.extend(f"{lang_code}: {w}" for w in entry_warnings)
            if resolved != latin:
                poll["latin"] = resolved
                changes.append(f"{lang_code}: {name!r}: {latin!r} -> {resolved!r}")
    return changes, warnings


def run_repair():
    """Revalidate the whole db offline and save it if anything changed."""
    db = load_db()
    if not db:
        print(f"No {DB_FILE} to repair.")
        return

    changes, warnings = repair_db(db)
    for warning in warnings:
        print(f"WARNING: {warning}")
    for change in changes:
        print(f"Repaired {change}")

    if changes:
        save_db(db)
        print(f"Done. {len(changes)} latin name(s) repaired in {DB_FILE}")
    else:
        print(f"Done. Nothing to repair in {DB_FILE}")


def run_fetch():
    """Fetch every language missing from the db and record its allergen names."""
    import requests
    from dotenv import load_dotenv

    load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../.env"))
    api_key = os.environ["API_KEY"]

    db = load_db()
    base_url = "https://www.polleninformation.at/api/forecast/public"

    for lang_code in LANG_CODES:
        if lang_code in db:
            print(f"{lang_code}: Already in db, skipping.")
            continue

        params = {
            "country": COUNTRY,
            "lang": lang_code,
            "latitude": LAT,
            "longitude": LON,
            "apikey": api_key,
        }
        try:
            resp = requests.get(base_url, params=params, headers=HEADERS, timeout=20)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"{lang_code}: [request error: {e}]")
            db[lang_code] = {"error": str(e), "lang_code": lang_code}
            save_db(db)
            time.sleep(DELAY_SEC)
            continue

        # Parse forecast block for title/allergens
        try:
            poll_titles, warnings = poll_titles_from_contamination(
                data.get("contamination", [])
            )
        except Exception as e:
            print(f"{lang_code}: [parse error: {e}]")
            db[lang_code] = {"error": f"parse error: {e}", "lang_code": lang_code}
            save_db(db)
            time.sleep(DELAY_SEC)
            continue

        for warning in warnings:
            print(f"{lang_code}: WARNING: {warning}")

        entry = {
            "lang_code": lang_code,
            "lang": get_language_name(lang_code),
            "poll_titles": poll_titles,
        }
        db[lang_code] = entry
        print(f"{lang_code}: OK, {len(poll_titles)} allergens")
        save_db(db)
        time.sleep(DELAY_SEC)

    print(f"Done. See {DB_FILE}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--repair",
        action="store_true",
        help=(
            "revalidate the latin names already in the file instead of "
            "fetching; needs no API key and no network"
        ),
    )
    args = parser.parse_args(argv)

    if args.repair:
        run_repair()
    else:
        run_fetch()


if __name__ == "__main__":
    main()
