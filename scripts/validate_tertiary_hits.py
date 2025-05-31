#!/usr/bin/env python3
import json
import os
import sys
import math
from datetime import datetime, timezone

# Kräver: pip install geopy reverse_geocoder
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
import reverse_geocoder as rg

DB_FILE = "country_ids.json"


# ---------------------------------------------------
# 1) Hjälpfunktion: läsa in JSON‐filen
# ---------------------------------------------------
def load_db():
    if not os.path.exists(DB_FILE):
        print(f"Fel: Kunde inte hitta {DB_FILE}.", file=sys.stderr)
        sys.exit(1)
    with open(DB_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data


# ---------------------------------------------------
# 2) Haversine‐funktion: avstånd i km mellan två punkter
# ---------------------------------------------------
def haversine(lat1, lon1, lat2, lon2):
    """
    Beräknar Haversine‐avståndet (i kilometer) mellan (lat1, lon1) och (lat2, lon2).
    """
    R = 6371.0  # Jordens radie i km
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


# ---------------------------------------------------
# 3) Initiera Geopy (för att geokoda "place_format")
# ---------------------------------------------------
geolocator = Nominatim(user_agent="validate_tertiary_dryrun/1.0")
# RateLimiter säkerställer att vi inte överskrider Nominatim‐tjänstens gränser
geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1, error_wait_seconds=2)


# ---------------------------------------------------
# 4) Reverse‐geocoding: lat/lon → country code
# ---------------------------------------------------
def reverse_geocode_country(lat: float, lon: float) -> str | None:
    """
    Returnerar landkoden (tvåkod, t.ex. 'FI', 'SE', 'LV') för (lat, lon) med reverse_geocoder.
    Om inget kan hittas, returnera None.
    """
    try:
        results = rg.search((lat, lon), mode=1)
    except Exception:
        return None

    if not results or len(results) == 0:
        return None

    cc = results[0].get("cc", None)
    return cc.upper() if isinstance(cc, str) else None


# ---------------------------------------------------
# 5) Huvudfunktion: “dry run” utan att skriva till JSON
# ---------------------------------------------------
def validate_tertiary_dryrun():
    db = load_db()

    print(f"==> Startar “dry run” validering: {DB_FILE}\n")

    for country_code, info in db.get("countries", {}).items():
        place_format = info.get("place_format", "").strip()
        lat_search = info.get("lat", None)
        lon_search = info.get("lon", None)

        # Om varken place_format eller lat/lon finns → skippa (men vi använder lat/lon endast för diagnostik)
        if not place_format:
            print(f"--- {country_code}: Ingen ‘place_format’ angiven → skippad.")
            continue

        print(f"\n=== {country_code}  «{place_format}» ===")

        # ------------------------------------------------------------------
        # 5a) Försök geokoda “place_format, <country_code>” (med land‐hint)
        # ------------------------------------------------------------------
        query_hint = f"{place_format}, {country_code}"
        try:
            location_hint = geocode(query_hint)
        except Exception as e:
            print(f"  [GEOPY‐FEL] Kunde inte köra geocode('{query_hint}'): {e}")
            geocoded = None
            geocode_method = None
        else:
            if location_hint:
                geocoded = (location_hint.latitude, location_hint.longitude)
                geocode_method = "med hint"
            else:
                geocoded = None
                geocode_method = None

        # ---------------------------------------------------
        # 5b) Om “med hint” misslyckades, försök utan hint
        # ---------------------------------------------------
        if geocoded is None:
            print(f"  [GEOPY] Ingen lat/lon funnen för “{query_hint}”.")
            # Försök geokoda enbart “place_format”
            query_no_hint = place_format
            try:
                location_no_hint = geocode(query_no_hint)
            except Exception as e:
                print(f"  [GEOPY‐FEL] Kunde inte köra geocode('{query_no_hint}'): {e}")
                geocoded = None
                geocode_method = None
            else:
                if location_no_hint:
                    geocoded = (location_no_hint.latitude, location_no_hint.longitude)
                    geocode_method = "utan hint"
                else:
                    geocoded = None
                    geocode_method = None

            if geocoded:
                lat_geo, lon_geo = geocoded
                print(f"    → Geokodning “utan hint” för “{query_no_hint}” → lat/lon = ({lat_geo:.5f}, {lon_geo:.5f})")
            else:
                print(f"    → Ingen lat/lon funnen för “{place_format}” utan hint.")

        else:
            lat_geo, lon_geo = geocoded
            print(f"  [GEOPY] Geokodning “{geocode_method}” för “{query_hint}” → lat/lon = ({lat_geo:.5f}, {lon_geo:.5f})")

        # ---------------------------------------------------
        # 5c) Om vi har en geokodat punkt → räkna ut avstånd (diagnostik)
        # ---------------------------------------------------
        if geocoded and lat_search is not None and lon_search is not None:
            dist_km = haversine(lat_search, lon_search, lat_geo, lon_geo)
            print(f"    • Avstånd (km) mellan sök‐koordinater ({lat_search},{lon_search}) "
                  f"och geokodat ({lat_geo:.5f},{lon_geo:.5f}) = {dist_km:.2f} km")

        # ---------------------------------------------------
        # 6) Reverse‐geocode med geokodat punkt (om geokodat finns)
        # ---------------------------------------------------
        if geocoded:
            rc_geo = reverse_geocode_country(lat_geo, lon_geo)
            if rc_geo:
                print(f"  [REV_GEO] Landkod från geokodat ({lat_geo:.5f},{lon_geo:.5f}) = '{rc_geo}'")
            else:
                print(f"  [REV_GEO] Kunde inte avgöra land från geokodat ({lat_geo:.5f},{lon_geo:.5f})")
        else:
            rc_geo = None

        # ---------------------------------------------------
        # 7) Slutsats jämfört med förväntat country_code
        # ---------------------------------------------------
        if not rc_geo:
            print("  ❓ Ingen giltig geokodat‐landkod – kan inte validera landet.")
            print("     → Markera denna post för manuell genomgång.")
            continue

        if rc_geo.upper() == country_code.upper():
            print(f"  ✅ Landkod “{rc_geo}” matchar förväntat “{country_code}”.")
        else:
            print(f"  ⚠️  Felaktig landmatchning: förväntat = “{country_code}”, "
                  f"men geokodat reverse_geocoder säger = “{rc_geo}”.")
            print("     → Detta är troligen en tertiär‐träff eller grannträff.")

    print("\n==> Klart med dry‐run (inga ändringar skrevs till JSON).")


if __name__ == "__main__":
    validate_tertiary_dryrun()

