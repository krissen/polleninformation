import json
import os
import time
import requests
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../.env"))

# ================================
# CONFIGURATION
# ================================

LAT = 48.2081743
LON = 16.3738189
COUNTRY = "AT"
API_KEY = os.environ["API_KEY"]
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


def main():
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
            "apikey": API_KEY,
        }
        try:
            resp = requests.get(base_url, params=params, headers=HEADERS, timeout=20)
            resp.raise_for_status()
            data = resp.json()
            contamination_date_1 = data.get("contamination_date_1")
        except Exception as e:
            print(f"{lang_code}: [request error: {e}]")
            db[lang_code] = {"error": str(e), "lang_code": lang_code}
            save_db(db)
            time.sleep(DELAY_SEC)
            continue

        # Parse forecast block for title/allergens
        try:
            contamination = data.get("contamination", [])
            poll_titles = []
            for poll in contamination:
                poll_title = poll.get("poll_title", "")
                # Split "name (Latin)" pattern
                if "(" in poll_title and ")" in poll_title:
                    name = poll_title.split("(", 1)[0].strip()
                    latin = poll_title.split("(", 1)[1].split(")", 1)[0].strip()
                else:
                    name = poll_title.strip()
                    latin = ""
                poll_titles.append(
                    {"name": name, "latin": latin, "poll_id": poll.get("poll_id")}
                )
        except Exception as e:
            print(f"{lang_code}: [parse error: {e}]")
            db[lang_code] = {"error": f"parse error: {e}", "lang_code": lang_code}
            save_db(db)
            time.sleep(DELAY_SEC)
            continue
        entry = {
            "lang_code": lang_code,
            "lang": get_language_name(lang_code),
            "contamination_date_1": contamination_date_1,
            "poll_titles": poll_titles,
        }
        db[lang_code] = entry
        print(f"{lang_code}: OK, {len(poll_titles)} allergens")
        save_db(db)
        time.sleep(DELAY_SEC)

    print(f"Done. See {DB_FILE}")


if __name__ == "__main__":
    main()
