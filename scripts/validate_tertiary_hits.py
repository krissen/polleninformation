#!/usr/bin/env python3
# coding: utf-8

import json
import os
import re
import signal
import unicodedata
from datetime import datetime, timezone
import math
import sys
import asyncio
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
from geopy.exc import GeocoderUnavailable, GeocoderTimedOut


# Tredjepartsbibliotek:
#   pip install geopy reverse_geocoder
import reverse_geocoder as rg

DB_FILE = "country_ids.json"

# Om det geokodade resultatet är mer än DISTANCE_THRESHOLD km bort
# från den ursprungliga sökkoordinaten, betraktas det som felaktigt.
DISTANCE_THRESHOLD = 100.0  # kilometer

should_exit = False  # flagga för Ctrl-C

# Lista över alla europeiska länder (ISO‐3166‐1 alpha‐2) med en exempeltstad och koordinater
EUROPEAN_LOCATIONS = [
    # Befintliga / redan listade
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
    # Saknade suveräna stater & mikroländer
    ("AL", 41.3275, 19.8187, "Tirana"),  # Albanien
    ("AD", 42.5063, 1.5218, "Andorra la Vella"),  # Andorra
    ("AM", 40.1792, 44.4991, "Yerevan"),  # Armenien
    ("AZ", 40.4093, 49.8671, "Baku"),  # Azerbajdzjan
    ("BA", 43.8563, 18.4131, "Sarajevo"),  # Bosnien & Herzegovina
    ("BY", 53.9006, 27.5590, "Minsk"),  # Vitryssland
    ("FO", 62.0078, -6.7908, "Tórshavn"),  # Färöarna
    ("GE", 41.7151, 44.8271, "Tbilisi"),  # Georgien
    ("IS", 64.1265, -21.8174, "Reykjavik"),  # Island
    ("KZ", 51.1605, 71.4704, "Astana"),  # Kazakstan (delvis i Europa)
    ("LI", 47.1660, 9.5554, "Vaduz"),  # Liechtenstein
    ("MK", 41.6086, 21.7453, "Skopje"),  # Nordmakedonien
    ("MD", 47.0105, 28.8638, "Chişinău"),  # Moldavien
    ("MC", 43.7384, 7.4246, "Monaco"),  # Monaco
    ("ME", 42.4304, 19.2594, "Podgorica"),  # Montenegro
    ("SM", 43.9354, 12.4475, "San Marino"),  # San Marino
    ("VA", 41.9029, 12.4534, "Vatican City"),  # Vatikanstaten
    ("XK", 42.6026, 20.9010, "Pristina"),  # Kosovo (kod ‘XK’ i UE‐system)
]


# ===============================================
# SIGNALHANTERING FÖR CTRL-C
# ===============================================


def handle_sigint(signum, frame):
    global should_exit
    should_exit = True


signal.signal(signal.SIGINT, handle_sigint)


# ===============================================
# HJÄLPFUNKTIONER FÖR SLUG OCH JSON-DATABAS
# ===============================================


def slugify(text: str) -> str:
    """
    Tar bort diakritiska tecken och ogiltiga tecken samt
    ersätter mellanslag/bindestreck med underscore.
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
    Extraherar bara själva ortsnamnet (utan postnummer eller liknande).
    Om första token är en “postnummer‐token” (bokstäver/siffror/bindestreck),
    tar vi bort den och slugifierar det som blir kvar.
    """
    full_location = full_location.strip()
    parts = full_location.split(maxsplit=1)
    if len(parts) == 2 and re.match(r"^[A-Za-z0-9\-]+$", parts[0]):
        place_name = parts[1]
    else:
        place_name = full_location
    return slugify(place_name)


def load_db():
    if not os.path.exists(DB_FILE):
        print(f"Fel: Kunde inte hitta {DB_FILE}.", file=sys.stderr)
        sys.exit(1)
    with open(DB_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    # Se till att “invalid” finns
    if "invalid" not in data:
        data["invalid"] = []
    return data


def save_db(db):
    temp_file = DB_FILE + ".tmp"
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)
    os.replace(temp_file, DB_FILE)


# ===============================================
# GEOKODNING / REVERSE-GEOCODE
# ===============================================

# 1) Initiera Geopy (för “place_format, <landkod>”)
geolocator = Nominatim(user_agent="polleninfo_validator", timeout=10)
geocode = RateLimiter(
    geolocator.geocode,
    min_delay_seconds=1,
    error_wait_seconds=5.0,
    swallow_exceptions=False,
)


def geocode_with_hint(place_format: str, country_code: str):
    """
    Försöker först med hint "place_format, country_code".
    Returnerar (lat, lon, metod) eller (None, None, None) om inget hittades.
    """
    # Först: försök med hint "place_format, country_code"
    query_hint = f"{place_format}, {country_code}"
    try:
        location = geocode(query_hint)
    except (GeocoderUnavailable, GeocoderTimedOut):
        return (None, None, None)
    except Exception:
        return (None, None, None)

    if location:
        return (location.latitude, location.longitude, "med hint")

    # Om ingen träff "med hint", pröva utan hint
    try:
        location_no_hint = geocode(place_format)
    except (GeocoderUnavailable, GeocoderTimedOut):
        return (None, None, None)
    except Exception:
        return (None, None, None)

    if location_no_hint:
        return (location_no_hint.latitude, location_no_hint.longitude, "utan hint")

    return (None, None, None)


def reverse_geocode_country(lat: float, lon: float) -> str | None:
    """
    Använder reverse_geocoder för att få landkod (tvåkod).
    Returnerar t.ex. "FI", "SE", "NO", annars None.
    """
    try:
        results = rg.search((lat, lon), mode=1)
    except Exception:
        return None
    if not results or len(results) == 0:
        return None
    cc = results[0].get("cc", None)
    return cc.upper() if isinstance(cc, str) else None


def haversine(lat1, lon1, lat2, lon2) -> float:
    """
    Beräknar Haversine‐avståndet (km) mellan två punkter.
    """
    R = 6371.0  # Jordens radie i km
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


# ===============================================
# HUVUDFUNKTION: VALIDERING SOM SKRIVER TILL JSON
# ===============================================


async def validate_and_write():
    global should_exit
    db = load_db()

    print(f"==> Startar validering med skrivning: {DB_FILE}\n")

    for country_code, info in db.get("countries", {}).items():
        if should_exit:
            print("\nAvslutar på användarens begäran (Ctrl-C).")
            break

        place_format = info.get("place_format", "").strip()
        lat_search = info.get("lat", None)
        lon_search = info.get("lon", None)

        print(f"\n=== {country_code}  «{place_format}» ===")

        # Om det redan finns en validation‐nyckel, hoppa över
        if "validation" in info:
            print("  ℹ️  Redan validerad (fälten 'validation' finns) → Hoppar över.")
            continue

        # --------- 1) Geokoda “place_format, country_code” eller “place_format” ----------
        lat_geo, lon_geo, method = geocode_with_hint(place_format, country_code)
        if lat_geo is not None and lon_geo is not None:
            print(
                f"  [GEOPY] Geokodning “{method}” för “{place_format}, {country_code}” → "
                f"lat/lon = ({lat_geo:.5f}, {lon_geo:.5f})"
            )
        else:
            print(
                f"  [GEOPY] Ingen lat/lon funnen för “{place_format}, {country_code}” varken med eller utan hint."
            )

        # --------- 2) Om vi inte hittade geokod, markera invalid och gå vidare ----------
        if lat_geo is None or lon_geo is None:
            reason = "ingen geokodning kunde göras"
            print(f"    ❌ {reason}, markerar VALIDATION.valid = false.")
            db["countries"][country_code]["validation"] = {
                "validated_at": datetime.now(timezone.utc).isoformat(),
                "valid": False,
                "reason": reason,
                "found_country": None,
                "distance_km": None,
            }
            save_db(db)
            continue

        # --------- 3) Reverse‐geocode landkod från (lat_geo, lon_geo) ----------
        rc_geo = reverse_geocode_country(lat_geo, lon_geo)
        if rc_geo:
            print(
                f"  [REV_GEO] Landkod från geokodat ({lat_geo:.5f},{lon_geo:.5f}) = '{rc_geo}'"
            )
        else:
            print(
                f"  [REV_GEO] Kunde inte avgöra land från geokodat ({lat_geo:.5f},{lon_geo:.5f})"
            )

        # --------- 4) Avståndskalkyl (om vi har sparade lat/lon) ----------
        if lat_search is not None and lon_search is not None:
            dist_km = haversine(lat_search, lon_search, lat_geo, lon_geo)
            print(
                f"    • Avstånd (km) mellan sparade sök‐koordinater ({lat_search:.4f},{lon_search:.4f}) "
                f"och geokodat ({lat_geo:.5f},{lon_geo:.5f}) = {dist_km:.2f} km"
            )
        else:
            dist_km = None

        # --------- 5) Jämför landkod + avstånd med förväntat landkod ----------
        if not rc_geo:
            # Inga landkod hittades → invalid
            reason = "ingen reverse_geocode‐landkod"
            print("    ❌ Ingen giltig geokodat‐landkod → markerar valid=false.")
            db["countries"][country_code]["validation"] = {
                "validated_at": datetime.now(timezone.utc).isoformat(),
                "valid": False,
                "reason": reason,
                "found_country": None,
                "distance_km": dist_km,
            }
            save_db(db)
            continue

        # a) Om landkoder skiljer sig → invalid
        if rc_geo.upper() != country_code.upper():
            reason = (
                f"felaktig landmatchning (förväntat={country_code}, geokodat={rc_geo})"
            )
            print(f"    ⚠️  {reason} → markerar valid=false.")
            db["countries"][country_code]["validation"] = {
                "validated_at": datetime.now(timezone.utc).isoformat(),
                "valid": False,
                "reason": reason,
                "found_country": rc_geo,
                "distance_km": dist_km,
            }
            save_db(db)
            continue

        # b) Landkod matchar – men kontrollera avstånd om vi har båda koordinaterna
        if dist_km is not None and dist_km > DISTANCE_THRESHOLD:
            reason = f"avstånd ({dist_km:.2f} km) > tröskel ({DISTANCE_THRESHOLD} km)"
            print(f"    ⚠️  {reason} → markerar valid=false.")
            db["countries"][country_code]["validation"] = {
                "validated_at": datetime.now(timezone.utc).isoformat(),
                "valid": False,
                "reason": reason,
                "found_country": rc_geo,
                "distance_km": dist_km,
            }
            save_db(db)
            continue

        # c) Om vi kommer hit betyder det att landkod matchar och avstånd är OK
        reason = "landkod matchade & avstånd OK"
        print(
            f"    ✅ Landkod “{rc_geo}” matchar förväntat “{country_code}” "
            f"och avstånd ({dist_km:.2f} km) är ≤ tröskel."
        )
        db["countries"][country_code]["validation"] = {
            "validated_at": datetime.now(timezone.utc).isoformat(),
            "valid": True,
            "reason": reason,
            "found_country": rc_geo,
            "distance_km": dist_km,
        }
        save_db(db)

    print("\n==> Klart! VALIDERINGSRESULTAT har skrivits till:", DB_FILE)


if __name__ == "__main__":
    import math
    from geopy.extra.rate_limiter import RateLimiter

    try:
        # Eftersom vi använder geopy + reverse_geocoder
        # behöver vi inte köra något asynkront i just denna loop –
        # men för enkelhets skull anropar vi funktionen med asyncio.run.
        asyncio.run(validate_and_write())
    except KeyboardInterrupt:
        print("\nAvslutar på användarens begäran (Ctrl-C).")
