#!/usr/bin/env python3
import json
import os
import re
import unicodedata
from datetime import datetime, timezone

DB_FILE = "country_ids.json"

def slugify(text: str) -> str:
    """
    Tar bort diakritiska tecken, ersätter mellanslag/bindestreck med _
    och tar bort all övrig icke-alfa-numerisk text.
    """
    if "(" in text:
        text = text.split("(", 1)[0]
    text = text.strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[\s\-]+", "_", text)
    text = re.sub(r"[^a-z0-9_]", "", text)
    return text

def extract_place_slug(full_location: str) -> str:
    """
    Extraherar bara själva ortsnamnet utan postnummer/lands-/zonkod.
    Om första token (före mellanslag) matchar ^[A-Za-z0-9\-]+$
    (t.ex. "9020", "LV-4242", "EC1A"), och det finns mer text efter,
    så kastar vi bort första token och slugifierar resten.
    Annars slugifierar vi hela full_location.
    """
    full_location = full_location.strip()
    parts = full_location.split(maxsplit=1)
    if len(parts) == 2 and re.match(r"^[A-Za-z0-9\-]+$", parts[0]):
        place_name = parts[1]
    else:
        place_name = full_location
    return slugify(place_name)

def migrate_slugs():
    if not os.path.exists(DB_FILE):
        print(f"Fel: Kunde inte hitta {DB_FILE}.")
        return

    with open(DB_FILE, "r", encoding="utf-8") as f:
        db = json.load(f)

    updated = False
    for country, info in db.get("countries", {}).items():
        old_slug = info.get("place_slug", "")
        place_format = info.get("place_format", "")
        if place_format:
            new_slug = extract_place_slug(place_format)
            if new_slug != old_slug:
                print(f"[MIGRATE] Land {country}: '{old_slug}' → '{new_slug}'")
                db["countries"][country]["place_slug"] = new_slug
                db["countries"][country]["last_updated"] = datetime.now(timezone.utc).isoformat()
                updated = True

    if updated:
        temp_file = DB_FILE + ".tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(db, f, indent=2, ensure_ascii=False)
        os.replace(temp_file, DB_FILE)
        print(f"\nMigration slutförd, skrev ny {DB_FILE}.")
    else:
        print("Inga ändringar behövde göras, alla slugs var redan korrekta.")

if __name__ == "__main__":
    migrate_slugs()

