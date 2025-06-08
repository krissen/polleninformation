#!/usr/bin/env python3
import asyncio
import json
import os
import re
import signal
import unicodedata
from datetime import datetime, timezone
from json.decoder import JSONDecodeError

import aiohttp
import async_timeout

# ===============================================
# KONFIGURATION
# ===============================================

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

REQUEST_DELAY = 3  # sekunder mellan API-anrop
DB_FILE = "country_ids.json"

EUROPEAN_LOCATIONS = [
    # --- Befintliga (allerade i er lista) ---
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
    # --- Saknade suveräna stater & mikroländer ---
    ("AL", 41.3275, 19.8187, "Tirana"),  # Albanien
    ("AD", 42.5063, 1.5218, "Andorra la Vella"),  # Andorra
    ("AM", 40.1792, 44.4991, "Yerevan"),  # Armenien
    ("AZ", 40.4093, 49.8671, "Baku"),  # Azerbajdzjan
    ("BA", 43.8563, 18.4131, "Sarajevo"),  # Bosnien & Herzegovina
    ("BY", 53.9006, 27.5590, "Minsk"),  # Vitryssland
    ("FO", 62.0078, -6.7908, "Tórshavn"),  # Färöarna
    ("GE", 41.7151, 44.8271, "Tbilisi"),  # Georgien
    ("IS", 64.1265, -21.8174, "Reykjavik"),  # Island
    ("KZ", 51.1605, 71.4704, "Astana"),  # Kazakstan (delvis Europa)
    ("LI", 47.1660, 9.5554, "Vaduz"),  # Liechtenstein
    ("MK", 41.6086, 21.7453, "Skopje"),  # Nordmakedonien
    ("MD", 47.0105, 28.8638, "Chişinău"),  # Moldavien
    ("MC", 43.7384, 7.4246, "Monaco"),  # Monaco
    ("ME", 42.4304, 19.2594, "Podgorica"),  # Montenegro
    ("SM", 43.9354, 12.4475, "San Marino"),  # San Marino
    ("VA", 41.9029, 12.4534, "Vatican City"),  # Vatikanstaten (Heliga stolen)
    ("XK", 42.6026, 20.9010, "Pristina"),  # Kosovo (ovanligt kodformat ‘XK’)
]

should_exit = False  # flagga för Ctrl-C

# ===============================================
# HJÄLPFUNKTIONER FÖR SLUG OCH JSON-DATABAS
# ===============================================


def slugify(text: str) -> str:
    """
    Konverterar en sträng (t.ex. 'Müglitz' eller 'Budakdoğanca') till en "slug"
    utan diakritiska tecken och utan ogiltiga tecken. Exempel:
      'Zürich'       -> 'zurich'
      'Müglitz'      -> 'muglitz'
      'Budakdoğanca' -> 'budakdoganca'
      'Villers-Sire-Nicole' -> 'villers_sire_nicole'
    """
    # 1) Ta bort allt efter eventuell parentes (t.ex. "Ipiķi (LV)" → "Ipiķi")
    if "(" in text:
        text = text.split("(", 1)[0]
    # 2) Trimma, gör till lower case
    text = text.strip().lower()
    # 3) Unicode‐normalize till NFKD och släng diakritiska tecken
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    # 4) Ersätt mellanslag och bindestreck med underscore
    text = re.sub(r"[\s\-]+", "_", text)
    # 5) Ta bort allt som inte är a–z, 0–9 eller underscore
    text = re.sub(r"[^a-z0-9_]", "", text)
    # 6) Slutresultat
    return text


def extract_place_slug(full_location: str) -> str:
    """
    Extraherar bara själva ortsnamnet, utan postnummer eller landskod.
    Om first token (separerad av mellanslag) är en kombination av siffror eller siffror/bindestreck
    (t.ex. "9020", "LV-4242", "EC1A"), så tar vi bort den tokenen.
    Resten normaliseras och slugifieras.
    """
    full_location = full_location.strip()
    parts = full_location.split(maxsplit=1)
    # Om första token innehåller antingen bara siffror eller en kombination av bokstäver/siffror/bindestreck
    # (t.ex. "9020", "LV-4242", "EC1A"), och det finns mer text efter, så skippar vi första token:
    if len(parts) == 2 and re.match(r"^[A-Za-z0-9\-]+$", parts[0]):
        place_name = parts[1]
    else:
        place_name = full_location
    return slugify(place_name)


def load_db():
    if not os.path.exists(DB_FILE):
        # Skapa grundstruktur med "invalid" om ny fil
        return {"countries": {}, "tested": {}, "invalid": []}
    with open(DB_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    # Se till att "invalid" finns
    if "invalid" not in data:
        data["invalid"] = []
    return data


def save_db(db):
    temp_file = DB_FILE + ".tmp"
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)
    os.replace(temp_file, DB_FILE)


def get_known_country_ids(db, country):
    entry = db["countries"].get(country)
    if not entry:
        return []
    return entry.get("country_ids", [])


def mark_country_ids(db, country, country_id, lat, lon, place_slug, place_format):
    entry = {
        "country_ids": [country_id],
        "lat": lat,
        "lon": lon,
        "place_slug": place_slug,
        "place_format": place_format,
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }
    db["countries"][country] = entry
    save_db(db)


def get_all_matched_ids(db):
    matched = set()
    for entry in db["countries"].values():
        for cid in entry.get("country_ids", []):
            matched.add(cid)
    return matched


def get_tested_ids(db, country):
    return set(db["tested"].get(country, []))


def get_invalid_ids(db):
    return set(db.get("invalid", []))


def is_tested(db, country, country_id):
    """
    Returnerar True om country_id:
      - Redan matchats (get_all_matched_ids)
      - Eller redan är testad för detta landet (tested)
    """
    if country_id in get_all_matched_ids(db):
        return True
    if country_id in get_tested_ids(db, country):
        return True
    return False


def mark_tested(db, country, country_id):
    if country not in db["tested"]:
        db["tested"][country] = []
    if country_id not in db["tested"][country]:
        db["tested"][country].append(country_id)
        save_db(db)


def mark_invalid(db, country_id):
    if "invalid" not in db:
        db["invalid"] = []
    if country_id not in db["invalid"]:
        db["invalid"].append(country_id)
        save_db(db)


# ===============================================
# ASYNCHRON FUNKTION FÖR API-ANROP
# ===============================================


async def fetch_pollen(
    lat: float, lon: float, country: str, country_id: int, lang: str = "de"
):
    url = POLLENAT_API_URL.format(
        lat=lat, lon=lon, country=country, country_id=country_id, lang=lang
    )
    try:
        async with async_timeout.timeout(10):
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    resp.raise_for_status()
                    text = await resp.text()
                    if not text.strip():
                        print(
                            f"    [DEBUG] fetch_pollen: tomt svar för country_id {country_id}"
                        )
                        return None
                    try:
                        payload = json.loads(text)
                        return payload.get("result", {})
                    except JSONDecodeError:
                        print(
                            f"    [DEBUG] fetch_pollen: ogiltigt JSON för country_id {country_id}"
                        )
                        return None
    except asyncio.CancelledError:
        raise
    except Exception as e:
        print(f"    [DEBUG] fetch_pollen exception: {e}")
        return None


# ===============================================
# HUVUDFUNKTION FÖR ATT UPPTÄCKA OCH SPARA I JSON
# ===============================================


async def discover_country_ids():
    global should_exit
    db = load_db()

    levels_de = ["keine Belastung", "gering", "mäßig", "hoch", "sehr hoch"]
    levels_en = ["none", "low", "moderate", "high", "very high"]

    for country, lat, lon, friendly_name in EUROPEAN_LOCATIONS:
        if should_exit:
            print("\nAvslutar på användarens begäran (Ctrl-C).")
            break

        print(f"\n=== {friendly_name} ({country}) ===")

        known_ids = get_known_country_ids(db, country)
        if known_ids:
            print(f"  ℹ️  Redan kända country_id: {known_ids} → Hoppar över testning.")
            continue

        matched_global = get_all_matched_ids(db)
        tested_local = get_tested_ids(db, country)
        invalid_global = get_invalid_ids(db)

        primary_ids = [
            cid
            for cid in range(1, 100)
            if cid not in matched_global
            and cid not in tested_local
            and cid not in invalid_global
        ]
        # secondary_ids = [
        #     cid
        #     for cid in sorted(invalid_global)
        #     if cid not in matched_global and cid not in tested_local
        # ]
        tertiary_ids = [
            cid for cid in sorted(matched_global) if cid not in tested_local
        ]

        found = False

        async def test_country_ids(id_list, pool_label):
            nonlocal found
            global should_exit
            for cid in id_list:
                if should_exit or found:
                    break

                print(
                    f"    [DEBUG] ({pool_label} pool) testar country_id = {cid} för {country}"
                )

                try:
                    result = await fetch_pollen(lat, lon, country, cid, lang="de")
                except asyncio.CancelledError:
                    should_exit = True
                    print("    [DEBUG] fetch_pollen avbröts (CancelledError).")
                    break

                if should_exit or found:
                    break

                if result is None:
                    print(
                        f"      [DEBUG] Inget giltigt resultat för country_id = {cid}, markerar som ogiltigt."
                    )
                    mark_invalid(db, cid)
                    mark_tested(db, country, cid)
                    try:
                        await asyncio.sleep(REQUEST_DELAY)
                    except asyncio.CancelledError:
                        should_exit = True
                        print("    [DEBUG] Sleep avbröts (CancelledError).")
                    continue
                else:
                    contamination = result.get("contamination", None)
                    print(f"      [DEBUG] Fick 'contamination': {contamination}")

                if contamination:
                    print(f"  ✅ Hittade data med country_id = {cid}")
                    example_place_format = result.get("locationtitle", "")
                    example_place_slug = extract_place_slug(example_place_format)
                    print(f"    – Platsnamn (API): {example_place_format}")
                    print(f"    – Slugifierad ort: {example_place_slug}")

                    first = contamination[0]
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
                        f"       Exempel entity_id: polleninformation_{example_place_slug}_{allergen_slug}\n"
                    )

                    print(
                        f"    [DEBUG] Markerar country_id {cid} som testad och sparar matchning."
                    )
                    mark_tested(db, country, cid)
                    mark_country_ids(
                        db,
                        country,
                        cid,
                        lat,
                        lon,
                        example_place_slug,
                        example_place_format,
                    )
                    found = True
                    break

                else:
                    print(
                        f"    [DEBUG] Giltigt JSON men ingen 'contamination' för country_id = {cid}, markerar som testad."
                    )
                    mark_tested(db, country, cid)
                    try:
                        await asyncio.sleep(REQUEST_DELAY)
                    except asyncio.CancelledError:
                        should_exit = True
                        print("    [DEBUG] Sleep avbröts (CancelledError).")
                        break

        # 1) Först testa primära IDs
        await test_country_ids(primary_ids, "primär")

        # 2) Om ingen match hittades, testa sekundära IDs
        # if not found and secondary_ids:
        # print("  ℹ️  Ingen match i primär pool, testar sekundär pool (tidigare markerade som ogiltiga)...")
        # await test_country_ids(secondary_ids, "sekundär")

        # 3) Om fortfarande ingen match, testa tertiary IDs (IDs som redan matchats för andra länder)
        if not found and tertiary_ids:
            print(
                "  ℹ️  Ingen match i primär eller sekundär pool, testar tertiary pool (matchade globalt)…"
            )
            await test_country_ids(tertiary_ids, "tertiär")

        if should_exit:
            break

        if not found:
            print(
                "  ❌ Ingen giltig data funnen för country_id 1–99 (inklusive ogiltiga och matchade)."
            )

    if not should_exit:
        print("\nKlart! Alla resultat har sparats i:", DB_FILE)


# ===============================================
# SIGNALHANTERING FÖR CTRL-C
# ===============================================


def handle_sigint(signum, frame):
    global should_exit
    should_exit = True


signal.signal(signal.SIGINT, handle_sigint)

# ===============================================
# KÖRNING
# ===============================================

if __name__ == "__main__":
    try:
        asyncio.run(discover_country_ids())
    except KeyboardInterrupt:
        print("\nAvslutar på användarens begäran (Ctrl-C).")
