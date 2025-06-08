#!/usr/bin/env python3
import argparse
import asyncio
import aiohttp
import async_timeout
import re
import sys

# ===============================================
# DEFAULT‐VÄRDEN FÖR URL‐PARAMETRAR
# ===============================================
DEFAULT_LANG = "de"
DEFAULT_LANG_ID = 0
DEFAULT_ACTION = "getFullContaminationData"
DEFAULT_TYPE = "gps"
DEFAULT_PERSONAL_CONTAMINATION = "false"
DEFAULT_SENSITIVITY = 0
DEFAULT_SESSIONID = ""


def build_url(
    lat: float,
    lon: float,
    country_code: str,
    country_id: int,
    lang: str,
    lang_id: int,
    action: str,
    type_param: str,
    personal_contamination: str,
    sensitivity: int,
    sessionid: str,
) -> str:
    """
    Bygger URL‐strängen för polleninformation.at med de givna parametrarna.
    """
    base = (
        "https://www.polleninformation.at/index.php"
        "?eID=appinterface"
        "&pure_json=1"
        "&lang_code={lang}"
        "&lang_id={lang_id}"
        "&action={action}"
        "&type={type_param}"
        "&value[latitude]={lat}"
        "&value[longitude]={lon}"
        "&country_id={country_id}"
        "&personal_contamination={personal_contamination}"
        "&sensitivity={sensitivity}"
        "&country={country_code}"
        "&sessionid={sessionid}"
    )
    return base.format(
        lang=lang,
        lang_id=lang_id,
        action=action,
        type_param=type_param,
        lat=lat,
        lon=lon,
        country_id=country_id,
        personal_contamination=personal_contamination,
        sensitivity=sensitivity,
        country_code=country_code,
        sessionid=sessionid,
    )


def slugify(text: str) -> str:
    """
    Gör en enkel slugifiering:
    - Klipper av vid första parentes (tar bort latinskt namn).
    - Gemener, ersätter tyska specialtecken: ö→o, ä→a, å→a, ß→ss.
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
    Tar emot hela platsnamnet, t.ex. "9020 Klagenfurt".
    Dela på mellanslag och ta bort första token om den är helt numerisk eller alfanumerisk
    (postnummer eller kod), sedan slugifiera resten.
    """
    full_location = full_location.strip()
    parts = full_location.split(maxsplit=1)
    if parts and re.match(r"^[A-Za-z0-9\-]+$", parts[0]) and len(parts) == 2:
        place_name = parts[1]
    else:
        place_name = full_location
    return slugify(place_name)


async def fetch_pollen(
    lat: float,
    lon: float,
    country_code: str,
    country_id: int,
    lang: str,
    lang_id: int,
    action: str,
    type_param: str,
    personal_contamination: str,
    sensitivity: int,
    sessionid: str,
) -> dict | None:
    """
    Hämtar pollen‐data och returnerar hela 'result'‐objektet som en dict.
    Vid fel returneras None.
    """
    url = build_url(
        lat=lat,
        lon=lon,
        country_code=country_code,
        country_id=country_id,
        lang=lang,
        lang_id=lang_id,
        action=action,
        type_param=type_param,
        personal_contamination=personal_contamination,
        sensitivity=sensitivity,
        sessionid=sessionid,
    )
    print(f"\nAnropar URL:\n  {url}\n")
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


async def main(args):
    # Utför API‐anropet
    result = await fetch_pollen(
        lat=args.lat,
        lon=args.lon,
        country_code=args.country,
        country_id=args.country_id,
        lang=args.lang,
        lang_id=args.lang_id,
        action=args.action,
        type_param=args.type,
        personal_contamination=str(args.personal_contamination).lower(),
        sensitivity=args.sensitivity,
        sessionid=args.sessionid,
    )
    if not result:
        print("Hämtningen misslyckades eller gav inget resultat.")
        return

    # Extrahera platsnamn och visa
    full_location = result.get("locationtitle", "Unknown Location")
    print(f"Platsnamn (locationtitle): {full_location}\n")

    # Bygg en slug av platsnamnet (utan postnummer eller kod)
    location_slug = extract_place_slug(full_location)
    print(f"Plats‐slug (utan postnummer/kod): {location_slug}\n")

    # Hämta pollen‐data
    contamination = result.get("contamination", [])
    if not contamination:
        print("Ingen 'contamination'-data funnen.")
        return

    # Definiera etiketter för tyska och engelska nivåer
    levels_de = ["keine Belastung", "gering", "mäßig", "hoch", "sehr hoch"]
    levels_en = ["none", "low", "moderate", "high", "very high"]

    print("Extraherad pollen‐lista (contamination):\n")
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

        # Hämta tysk etikett (med skydd mot IndexError/TypeError)
        try:
            level_text_de = levels_de[raw_val]
        except (IndexError, TypeError):
            level_text_de = "unavailable"

        # Hämta engelsk etikett
        level_text_en = (
            levels_en[raw_val] if 0 <= raw_val < len(levels_en) else "unavailable"
        )

        print(f"  – Allergen: {raw_title}")
        print(f"    Tyskt namn: {german_part}")
        print(f"    Latinskt namn: {latin_part}")
        print(f"    Slugifierat allergen‐namn: {allergen_slug}")
        print(f"    Raw: {raw_val}")
        print(f"    Tyska etiketten: {level_text_de}")
        print(f"    Engelska etiketten: {level_text_en}")
        print(
            f"    Kommande entity_id skulle kunna bli: polleninformation_{location_slug}_{allergen_slug}\n"
        )


def parse_args():
    parser = argparse.ArgumentParser(
        description="Testscript för polleninformation.at – kan ange alla GET‐parametrar via switchar."
    )

    parser.add_argument(
        "--lat", type=float, required=True, help="Latitud för platsen (t.ex. 46.628)."
    )
    parser.add_argument(
        "--lon", type=float, required=True, help="Longitud för platsen (t.ex. 14.309)."
    )
    parser.add_argument(
        "--country",
        type=str,
        default="AT",
        help="Landskod (ISO alpha‐2) för API:t (standard: AT).",
    )
    parser.add_argument(
        "--country-id",
        type=int,
        default=1,
        help="Numerisk country_id‐parameter (standard: 1).",
    )
    parser.add_argument(
        "--lang",
        type=str,
        default=DEFAULT_LANG,
        help=f"Språkkod för API:t (standard: {DEFAULT_LANG}).",
    )
    parser.add_argument(
        "--lang-id",
        type=int,
        default=DEFAULT_LANG_ID,
        help=f"Numerisk lang_id (standard: {DEFAULT_LANG_ID}).",
    )
    parser.add_argument(
        "--action",
        type=str,
        default=DEFAULT_ACTION,
        help=f"Action‐parameter för API:t (standard: {DEFAULT_ACTION}).",
    )
    parser.add_argument(
        "--type",
        type=str,
        dest="type",
        default=DEFAULT_TYPE,
        help=f"Type‐parameter för API:t (standard: {DEFAULT_TYPE}).",
    )
    parser.add_argument(
        "--personal-contamination",
        action="store_true",
        help="Sätt denna flagga för personal_contamination=true, annars false.",
    )
    parser.add_argument(
        "--sensitivity",
        type=int,
        default=DEFAULT_SENSITIVITY,
        help=f"Sensitivity‐parameter (0–?... standard: {DEFAULT_SENSITIVITY}).",
    )
    parser.add_argument(
        "--sessionid",
        type=str,
        default=DEFAULT_SESSIONID,
        help="Sessionid‐parameter (standard: tom).",
    )

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    # Konvertera boolean‐flaggan till str(True/False)
    args.personal_contamination = "true" if args.personal_contamination else "false"

    try:
        asyncio.run(main(args))
    except KeyboardInterrupt:
        print("\nAvbröts av användaren (Ctrl-C).")
        sys.exit(1)
