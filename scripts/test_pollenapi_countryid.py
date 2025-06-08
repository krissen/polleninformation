import asyncio
import aiohttp
import async_timeout
import re
import json
import os
from datetime import datetime

# ===============================================
# KONFIGURATION
# ===============================================

# Mall-URL för polleninformation.at API. Vi håller kvar parametern country_id dynamiskt.
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

# Fördröjning (sekunder) mellan API-anrop
REQUEST_DELAY = 3

# Filnamn för JSON‐“databas”
DB_FILE = "country_ids.json"

# Lista över europeiska länder att testa, med en representativ lat/lon (ofta huvudstad):
# (landskod, lat, lon, "vänligt namn")
EUROPEAN_LOCATIONS = [
    ("AT", 46.628, 14.309, "Klagenfurt"),
    ("BE", 50.8503, 4.3517, "Brussels"),
    ("BG", 42.6977, 23.3219, "Sofia"),
    ("CH", 47.3769, 8.5417, "Zurich"),
    ("CY", 35.1856, 33.3823, "Nicosia"),
    ("CZ", 50.0755, 14.4378, "Prague"),
    ("DE", 52.5200, 13.4050, "Berlin"),
    ("DK", 55.6761, 12.5683, "Copenhagen"),
    ("EE", 59.4369, 24.7535, "Tallinn"),
    ("ES", 40.4168, -3.7038, "Madrid"),
    ("FI", 60.1699, 24.9384, "Helsinki"),
    ("FR", 48.8566, 2.3522, "Paris"),
    ("GB", 51.5074, -0.1278, "London"),
    ("GR", 37.9838, 23.7275, "Athens"),
    ("HR", 45.8150, 15.9819, "Zagreb"),
    ("HU", 47.4979, 19.0402, "Budapest"),
    ("IE", 53.3498, -6.2603, "Dublin"),
    ("IT", 41.9028, 12.4964, "Rome"),
    ("LT", 54.6872, 25.2797, "Vilnius"),
    ("LU", 49.6116, 6.1319, "Luxembourg"),
    ("LV", 56.9496, 24.1052, "Riga"),
    ("MT", 35.8989, 14.5146, "Valletta"),
    ("NL", 52.3676, 4.9041, "Amsterdam"),
    ("NO", 59.9139, 10.7522, "Oslo"),
    ("PL", 52.2297, 21.0122, "Warsaw"),
    ("PT", 38.7223, -9.1393, "Lisbon"),
    ("RO", 44.4268, 26.1025, "Bucharest"),
    ("RS", 44.7866, 20.4489, "Belgrade"),
    ("SE", 59.3293, 18.0686, "Stockholm"),
    ("SI", 46.0569, 14.5058, "Ljubljana"),
    ("SK", 48.1486, 17.1077, "Bratislava"),
    ("TR", 39.9334, 32.8597, "Ankara"),
    ("UA", 50.4501, 30.5234, "Kyiv"),
    # Lägg till fler vid behov...
]

# ===============================================
# HJÄLPFUNKTIONER FÖR SLUG OCH JSON-DATABAS
# ===============================================


def slugify(text: str) -> str:
    """
    Enkel slugifiering:
    - Klipper av vid första parentes (tar bort latinskt namn).
    - Gemener, ersätter ö,ä,å med o,a,a och ß med ss.
    - Ersätter mellanslag med underscore.
    - Tar bort allt som inte är a–z, 0–9 eller underscore.
    """
    if "(" in text:
        text = text.split("(", 1)[0]
    text = text.strip().lower()
    text = text.replace("ö", "o").replace("ä", "a").replace("å", "a").replace("ß", "ss")
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"[^a-z0-9_]", "", text)
    return text


def extract_place_slug(full_location: str) -> str:
    """
    Tar emot hela platsnamnet, t.ex. "9020 Klagenfurt" eller "75001 Paris".
    Om första token är postnummer (enbart siffror), tas den bort.
    Returnerar den slugifierade orten, t.ex. "klagenfurt" eller "paris".
    """
    full_location = full_location.strip()
    parts = full_location.split()
    if parts and parts[0].isdigit():
        place_name = " ".join(parts[1:])
    else:
        place_name = full_location
    return slugify(place_name)


def load_db():
    """
    Läs in JSON-databasen från fil (om den finns). Annars returnera tom struktur.
    Struktur:
    {
      "countries": {
         "<country>": {
            "country_ids": [1, 7, ...],
            "lat": <float>,
            "lon": <float>,
            "place_slug": "<slug>",
            "last_updated": "<ISO-timestamp>"
         },
         ...
      },
      "tested": {
         "<country>": [<tested_id1>, <tested_id2>, ...],
         ...
      }
    }
    """
    if not os.path.exists(DB_FILE):
        return {"countries": {}, "tested": {}}
    with open(DB_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_db(db):
    """
    Skriv JSON-objektet 'db' till fil (atomärt).
    """
    temp_file = DB_FILE + ".tmp"
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)
    os.replace(temp_file, DB_FILE)


def get_known_country_ids(db, country):
    """
    Returnerar listan av redan funna country_id för <country>, eller [] om ingen.
    """
    entry = db["countries"].get(country)
    if not entry:
        return []
    return entry.get("country_ids", [])


def mark_country_ids(db, country, ids_list, lat, lon, place_slug):
    """
    Skapa eller uppdatera posten i db["countries"][country] med
    - country_ids: unik sorterad lista av ints
    - lat, lon, place_slug, last_updated
    """
    ids_sorted = sorted(set(ids_list))
    entry = {
        "country_ids": ids_sorted,
        "lat": lat,
        "lon": lon,
        "place_slug": place_slug,
        "last_updated": datetime.utcnow().isoformat(),
    }
    db["countries"][country] = entry
    save_db(db)


def is_tested(db, country, country_id):
    """
    Kollar om <country_id> redan finns i db["tested"][country].
    """
    tested_ids = db["tested"].get(country, [])
    return country_id in tested_ids


def mark_tested(db, country, country_id):
    """
    Lägger till <country_id> i listan db["tested"][country].
    """
    if country not in db["tested"]:
        db["tested"][country] = []
    if country_id not in db["tested"][country]:
        db["tested"][country].append(country_id)
        save_db(db)


# ===============================================
# ASYNC-FUNKTION FÖR API-ANROP
# ===============================================


async def fetch_pollen(
    lat: float, lon: float, country: str, country_id: int, lang: str = "de"
):
    """
    Hämtar pollen-data (result) för en given lat/lon, country‐kod och country_id.
    Returnerar None vid fel, annars en dict som innehåller:
      - "locationtitle"  (t.ex. "9020 Klagenfurt", "75001 Paris" osv)
      - "contamination": [lista av pollen‐objekt]
    """
    url = POLLENAT_API_URL.format(
        lat=lat, lon=lon, country=country, country_id=country_id, lang=lang
    )
    try:
        async with async_timeout.timeout(10):
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    resp.raise_for_status()
                    payload = await resp.json()
                    return payload.get("result", {})
    except Exception:
        return None


# ===============================================
# HUVUDFUNKTION FÖR ATT TESTA OCH SPARA I JSON
# ===============================================


async def discover_country_ids():
    """
    Gå igenom alla EUROPEAN_LOCATIONS. För varje land:
      1. Läs in redan kända country_id från JSON-db.
      2. Om kända finns, hoppa över testning.
      3. Annars: testa country_id 1–99, hoppa över redan testade (db["tested"]).
      4. Markera varje testad country_id i db["tested"].
      5. Om vi finner data för ett country_id, lägg till det i lokal lista found_ids.
         Visa första som ✓ och eventuella ytterligare som 🔄.
      6. Efter varje anrop, vänta REQUEST_DELAY sekunder.
      7. Om found_ids inte tom, spara i db["countries"] med mark_country_ids.
      8. Spara JSON-databasen kontinuerligt (efter varje uppdatering).
    """
    db = load_db()

    levels_de = ["keine Belastung", "gering", "mäßig", "hoch", "sehr hoch"]
    levels_en = ["none", "low", "moderate", "high", "very high"]

    for country, lat, lon, friendly_name in EUROPEAN_LOCATIONS:
        print(f"\n=== {friendly_name} ({country}) ===")
        known_ids = get_known_country_ids(db, country)
        if known_ids:
            print(f"  ℹ️  Redan kända country_id: {known_ids} → Hoppar över testning.")
            continue

        found_ids = []
        place_slug_example = ""

        for country_id in range(1, 100):
            # Hoppa över om redan testat
            if is_tested(db, country, country_id):
                continue

            result = await fetch_pollen(lat, lon, country, country_id, lang="de")
            mark_tested(
                db, country, country_id
            )  # Spara som testad, oavsett om giltig eller ej
            await asyncio.sleep(REQUEST_DELAY)

            if result and result.get("contamination"):
                if not found_ids:
                    print(f"  ✅ Hittade data med country_id = {country_id}")
                    full_location = result.get("locationtitle", "Unknown Location")
                    place_slug_example = extract_place_slug(full_location)
                    print(f"    – Platsnamn från API: {full_location}")
                    print(f"    – Slugifierat platsnamn: {place_slug_example}")
                else:
                    print(f"  🔄 Också fungerande country_id = {country_id}")

                found_ids.append(country_id)

                # Visa ett exempel på allergen från listan
                first = result["contamination"][0]
                raw_title = first.get("poll_title", "<okänt>")
                raw_val = first.get("contamination_1", 0)

                if "(" in raw_title and ")" in raw_title:
                    german_part = raw_title.split("(", 1)[0].strip()
                    latin_part = raw_title.split("(", 1)[1].split(")", 1)[0].strip()
                else:
                    german_part = raw_title.strip()
                    latin_part = ""

                allergen_slug = slugify(german_part)
                level_text_de = (
                    levels_de[raw_val]
                    if 0 <= raw_val < len(levels_de)
                    else "unavailable"
                )
                level_text_en = (
                    levels_en[raw_val]
                    if 0 <= raw_val < len(levels_en)
                    else "unavailable"
                )

                print("    – Exempel‐allergen:")
                print(f"       Tyskt namn: {german_part}")
                print(f"       Latinskt: {latin_part}")
                print(f"       Slugifierat: {allergen_slug}")
                print(f"       Raw: {raw_val}")
                print(f"       Tyska etiketten: {level_text_de}")
                print(f"       Engelska etiketten: {level_text_en}")
                print(
                    f"       Exempel entity_id: polleninformation_{place_slug_example}_{allergen_slug}\n"
                )

        if not found_ids:
            print("  ❌ Ingen giltig data funnen för country_id 1–99.")
        else:
            mark_country_ids(db, country, found_ids, lat, lon, place_slug_example)

    print("\nKlart! Alla resultat har sparats i", DB_FILE)


# ===============================================
# KÖRNING
# ===============================================

if __name__ == "__main__":
    asyncio.run(discover_country_ids())
