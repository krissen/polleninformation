import asyncio
import aiohttp
import async_timeout
import re

# URL‐mall för anrop till polleninformation.at (med {lat}, {lon}, {country}, {lang})
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
    # Klipp av vid parentes, om sådan finns
    if "(" in text:
        text = text.split("(", 1)[0]
    text = text.strip().lower()
    # Ersätt tyska specialtecken
    text = (
        text.replace("ö", "o")
            .replace("ä", "a")
            .replace("å", "a")
            .replace("ß", "ss")
    )
    # Ersätt mellanslag (och flera) med underscore
    text = re.sub(r"\s+", "_", text)
    # Ta bort allt som inte är a–z, 0–9 eller underscore
    text = re.sub(r"[^a-z0-9_]", "", text)
    return text

def extract_place_slug(full_location: str) -> str:
    """
    Tar emot hela platsnamnet, till exempel "9020 Klagenfurt".
    Dela på mellanslag och ta bort första token om den är helt numerisk (postnummer).
    Returnera den slugifierade orten, till exempel "klagenfurt".
    """
    full_location = full_location.strip()
    parts = full_location.split()
    if parts and parts[0].isdigit():
        place_name = " ".join(parts[1:])
    else:
        place_name = full_location
    return slugify(place_name)

async def fetch_pollen(lat: float, lon: float, country: str = "AT", lang: str = "de"):
    """Hämtar pollen-data och returnerar hela 'result'‐objektet."""
    url = POLLENAT_API_URL.format(lat=lat, lon=lon, country=country, lang=lang)
    print(f"Anropar URL:\n  {url}\n")
    try:
        async with async_timeout.timeout(10):
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    resp.raise_for_status()
                    payload = await resp.json()
                    return payload.get("result", {})
    except Exception as e:
        print("Fel vid anrop:", e)
        return None

if __name__ == "__main__":
    # Testkoordinater
    lat_test = 46.628
    lon_test = 14.309
    country_test = "AT"
    lang_test = "de"  # Vi vill få poll_title på tyska

    result = asyncio.run(fetch_pollen(lat_test, lon_test, country_test, lang_test))
    if not result:
        print("Hämtningen misslyckades.")
        exit(1)

    # Extrahera platsnamn och visa
    full_location = result.get("locationtitle", "Unknown Location")
    print(f"Platsnamn (locationtitle): {full_location}\n")

    # Bygg en slug av platsnamnet (utan postnummer)
    location_slug = extract_place_slug(full_location)
    print(f"Plats‐slug (utan postnummer): {location_slug}\n")

    # Hämta pollen-data
    contamination = result.get("contamination", [])
    if not contamination:
        print("Ingen 'contamination'-data funnen.")
        exit(0)

    # Definiera etiketter för tyska och engelska nivåer
    levels_de = ["keine Belastung", "gering", "mäßig", "hoch", "sehr hoch"]
    levels_en = ["none", "low", "moderate", "high", "very high"]

    print("Extraherad pollen-lista (contamination):\n")
    for item in contamination:
        raw_title = item.get("poll_title", "<okänt>")
        raw_val = item.get("contamination_1", 0)

        # Dela råtitel på parentes för att få tyska och latinska namn
        if "(" in raw_title and ")" in raw_title:
            german_part = raw_title.split("(", 1)[0].strip()
            latin_part = raw_title.split("(", 1)[1].split(")", 1)[0].strip()
        else:
            german_part = raw_title.strip()
            latin_part = ""

        # Slugifiera det tyska namnet (utan latinskt namn)
        allergen_slug = slugify(german_part)

        # Hämta tysk etikett
        try:
            level_text_de = levels_de[raw_val]
        except (IndexError, TypeError):
            level_text_de = "unavailable"

        # Hämta engelsk etikett
        level_text_en = levels_en[raw_val] if 0 <= raw_val < len(levels_en) else "unavailable"

        print(f"  – Allergen: {raw_title}")
        print(f"    Tyskt namn: {german_part}")
        print(f"    Latinskt namn: {latin_part}")
        print(f"    Slugifierat allergen‐namn: {allergen_slug}")
        print(f"    Raw: {raw_val}")
        print(f"    Tyska etiketten: {level_text_de}")
        print(f"    Engelska etiketten: {level_text_en}")
        print(f"    Kommande entity_id skulle kunna bli: polleninformation_{location_slug}_{allergen_slug}\n")

