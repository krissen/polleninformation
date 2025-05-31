import asyncio
import aiohttp
import async_timeout
import re

# API‐mall för anrop till polleninformation.at (fungerar för alla länder via rätt country‐kod)
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
    "&country_id=1"
    "&personal_contamination=false"
    "&sensitivity=0"
    "&country={country}"
)

def slugify(text: str) -> str:
    """
    Gör en enkel slugifiering:
    - Klipper av vid första parentes (tar bort latinskt namn).
    - Gemener, ersätter ö,ä,å med o,a,a och ß med ss.
    - Ersätter mellanslag med underscore.
    - Tar bort allt som inte är a–z, 0–9 eller underscore.
    """
    if "(" in text:
        text = text.split("(", 1)[0]
    text = text.strip().lower()
    text = (
        text.replace("ö", "o")
            .replace("ä", "a")
            .replace("å", "a")
            .replace("ß", "ss")
    )
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"[^a-z0-9_]", "", text)
    return text

def extract_place_slug(full_location: str) -> str:
    """
    Tar emot hela platsnamnet, t.ex. "9020 Klagenfurt" eller "Paris".
    Om första token är postnummer (siffror), tas det bort.
    Returnerar den slugifierade orten, t.ex. "klagenfurt" eller "paris".
    """
    full_location = full_location.strip()
    parts = full_location.split()
    if parts and parts[0].isdigit():
        place_name = " ".join(parts[1:])
    else:
        place_name = full_location
    return slugify(place_name)

async def fetch_pollen(lat: float, lon: float, country: str, lang: str = "de"):
    """
    Hämtar pollen-data (result) för en given lat/long och country‐kod.
    Returnerar None vid fel, annars en dict som innehåller:
      - "locationtitle"  (t.ex. "9020 Klagenfurt" eller "75001 Paris")
      - "contamination": [lista av pollen‐objekt]
    """
    url = POLLENAT_API_URL.format(lat=lat, lon=lon, country=country, lang=lang)
    try:
        async with async_timeout.timeout(10):
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    resp.raise_for_status()
                    payload = await resp.json()
                    return payload.get("result", {})
    except Exception as e:
        print(f"  ❌ Fel vid anrop for {country} ({lat},{lon}): {e}")
        return None

async def test_multiple_locations():
    """
    Loopa över en uppsättning fördefinierade länder och koordinater.
    Skriver ut en sammanfattning för varje plats.
    """
    # Lista över länder och exempel‐lat/long
    locations = [
        ("AT", 46.628, 14.309, "Klagenfurt"),      # Österrike
        ("FR", 48.8566, 2.3522, "Paris"),          # Frankrike
        ("IT", 41.9028, 12.4964, "Rome"),          # Italien
        ("ES", 40.4168, -3.7038, "Madrid"),        # Spanien
        ("GB", 51.5074, -0.1278, "London"),        # Storbritannien
        ("DE", 52.5200, 13.4050, "Berlin"),        # Tyskland
    ]

    # Tyska och engelska etiketter för pollen-nivåer (0–4)
    levels_de = ["keine Belastung", "gering", "mäßig", "hoch", "sehr hoch"]
    levels_en = ["none", "low", "moderate", "high", "very high"]

    for country, lat, lon, friendly_name in locations:
        print(f"\n=== {friendly_name} ({country}) ===")
        result = await fetch_pollen(lat, lon, country, lang="de")
        if not result:
            print("  → Ingen data returned.\n")
            continue

        # Extrahera platsnamn exempelvis "75001 Paris" eller "9020 Klagenfurt"
        full_location = result.get("locationtitle", "Unknown Location")
        place_slug = extract_place_slug(full_location)
        print(f"  Platsnamn från API: {full_location}")
        print(f"  Slugifierat platsnamn (utan postnummer): {place_slug}\n")

        contamination = result.get("contamination", [])
        if not contamination:
            print("  → Ingen 'contamination'-data funnen.\n")
            continue

        print("  Pollen‐nivåer:")
        for item in contamination:
            raw_title = item.get("poll_title", "<okänt>")
            raw_val = item.get("contamination_1", 0)

            # Dela upp på parentes för tyska + latinska namn
            if "(" in raw_title and ")" in raw_title:
                german_part = raw_title.split("(", 1)[0].strip()
                latin_part = raw_title.split("(", 1)[1].split(")", 1)[0].strip()
            else:
                german_part = raw_title.strip()
                latin_part = ""

            # Slugifiera det tyska namnet
            allergen_slug = slugify(german_part)

            # Hämta etiketter
            level_text_de = levels_de[raw_val] if 0 <= raw_val < len(levels_de) else "unavailable"
            level_text_en = levels_en[raw_val] if 0 <= raw_val < len(levels_en) else "unavailable"

            # Skriv ut sammanfattning rad för rad
            print(f"    • {german_part} (Latin: {latin_part})")
            print(f"      - Slugifierat allergen: {allergen_slug}")
            print(f"      - Raw‐värde: {raw_val}")
            print(f"      - Tyska etiketten: {level_text_de}")
            print(f"      - Engelska etiketten: {level_text_en}")
            print(f"      - Exempel entity_id: polleninformation_{place_slug}_{allergen_slug}\n")


if __name__ == "__main__":
    asyncio.run(test_multiple_locations())

