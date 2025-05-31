#!/usr/bin/env python3
import json
import os
import re
import sys
from datetime import datetime, timezone

import pandas as pd

# Externa beroenden:
#   pip install pgeocode pandas geopy reverse_geocoder
import pgeocode
import reverse_geocoder as rg
from geopy.extra.rate_limiter import RateLimiter
from geopy.geocoders import Nominatim

DB_FILE = "country_ids.json"

# -----------------------------------------------
# 1) Hjälpfunktioner för postnummer och JSON‐databas
# -----------------------------------------------


def extract_postal_and_prefix(place_format: str):
    """
    Plockar ut (prefix, postnummer) ur en sträng som t.ex.:
      - "LV-4248 Arakste"  → ("LV", "4248")
      - "EC1A London"      → ("EC", "1")    (Vi får prefix="EC", postal="1")
      - "01778 Müglitz"    → (None, "01778")
      - "10435 Berlin"     → (None, "10435")
      - "75004 Paris"      → (None, "75004")
    Om ingen match, returnerar (None,None).
    """
    pf = place_format.strip()

    # a) Prefix (2 stora bokstäver) + bindestreck/mellanslag + siffror
    m = re.match(r"^([A-Z]{2})[-\s]?(\d+)", pf)
    if m:
        return m.group(1), m.group(2)

    # b) Enbart siffror i början
    m2 = re.match(r"^(\d+)", pf)
    if m2:
        return None, m2.group(1)

    return None, None


def load_db():
    if not os.path.exists(DB_FILE):
        print(f"Fel: Kunde inte hitta {DB_FILE}.", file=sys.stderr)
        sys.exit(1)
    with open(DB_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    if "invalid" not in data:
        data["invalid"] = []
    return data


def save_db(db):
    temp_file = DB_FILE + ".tmp"
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)
    os.replace(temp_file, DB_FILE)


# -----------------------------------------------
# 2) pgeocode‐baserad postnummer→land‐uppslagning
# -----------------------------------------------


def lookup_postcode_country(postcode: str, country_code: str) -> str | None:
    """
    Givet ett postnummer (t.ex. "4248") och en ISO‐landskod (t.ex. "lv" eller "FI"),
    returnerar vi med pgeocode den faktiska landkoden (tvåkod, t.ex. "LV" eller "FI")
    om uppslaget lyckas. Om pgeocode inte känner till landet eller postnumret, returnera None.
    """
    try:
        nomi = pgeocode.Nominatim(country_code.lower())
    except ValueError:
        # Om pgeocode inte har någon datakälla för t.ex. "ec"
        return None

    res = nomi.query_postal_code(postcode)
    if res is None:
        return None

    cc = res.get("country_code", pd.NA)
    # Om pgeocode returnerar NaN eller None
    if cc is pd.NA or (isinstance(cc, float) and pd.isna(cc)):
        return None

    # Vissa versioner returnerar bytestring
    if isinstance(cc, bytes):
        cc = cc.decode("utf-8")
    return cc


# -----------------------------------------------
# 3) Reverse‐geocoding med geopy + reverse_geocoder
# -----------------------------------------------

# Initiera geopy‐klient med viss ratelimit (1 sekund mellan förfrågningar)
geolocator = Nominatim(user_agent="pollen_validation_script/1.0")
geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1, error_wait_seconds=2)


def geocode_place(place_format: str, country_hint: str) -> tuple[float, float] | None:
    """
    Anropar geopy för att slå upp lat/lon av orten. Vi skickar med en "landshint"
    för att höja träffsäkerheten, exempelvis "Paris, FR", "Berlin, DE".
    Om geopy misslyckas returnerar vi None.
    """
    # Kombinera t.ex. "75004 Paris" + ", FR"
    query = f"{place_format}, {country_hint}"
    try:
        loc = geocode(query)
    except Exception as e:
        # T.ex. om vi får nätverksfel eller quota‐problem
        return None

    if loc is None:
        return None
    return (loc.latitude, loc.longitude)


def reverse_geocode_country(lat: float, lon: float) -> str | None:
    """
    Använder reverse_geocoder för att mappa (lat, lon) till närmaste stad, och
    returnerar dess country code (tvåkod). Om inget lyckas, returnera None.
    """
    try:
        results = rg.search((lat, lon), mode=1)  # mode=1 = frisökning
    except Exception:
        return None

    if not results or len(results) == 0:
        return None

    # results[0] är en dict med bl.a. 'cc'
    cc = results[0].get("cc", None)
    return cc.upper() if isinstance(cc, str) else None


# -----------------------------------------------
# 4) Huvudfunktion: validera tertiära träffar
# -----------------------------------------------


def validate_tertiary_hits():
    db = load_db()
    updated = False

    for country, info in db.get("countries", {}).items():
        # Hoppa över redan validerade poster
        if "country_found" in info or "validation_uncertain" in info:
            continue

        place_format = info.get("place_format", "").strip()
        print(f"\n=== Validerar {country} → '{place_format}' ===")

        if not place_format:
            # Inget place_format överhuvudtaget ⇒ uncertainty
            info["validation_uncertain"] = True
            info["last_validated"] = datetime.now(timezone.utc).isoformat()
            updated = True
            print("  [Utläsning] Inget place_format, markeras som uncertain.")
            continue

        # Första försöket: strippa ut prefix + postnummer
        prefix, postal = extract_postal_and_prefix(place_format)
        true_country = None

        # Försök 1: pgeocode med prefix (om finns)
        if postal:
            if prefix:
                print(
                    f"  [Steg 1] Försöker pgeocode med prefix='{prefix}', postnummer='{postal}'"
                )
                true_country = lookup_postcode_country(postal, prefix)
                if true_country:
                    print(
                        f"    [pgeocode] Hittade land='{true_country}' via prefix‐uppslag."
                    )

            # Om prefixuppslaget gav None, försök med antaget land
            if true_country is None:
                print(
                    f"  [Steg 2] pgeocode med antaget land='{country}', postnummer='{postal}'"
                )
                true_country = lookup_postcode_country(postal, country)
                if true_country:
                    print(
                        f"    [pgeocode] Hittade land='{true_country}' via antaget land."
                    )

        # Fall A: pgeocode sade None (eller postnummer var inte extraherat) → fallback till geopy + reverse_geocoder
        if true_country is None:
            # (i detta läge kanske postal==None också)
            print("  [Fallback] pgeocode kunde inte avgöra, försöker reverse‐geocode…")

            coords = geocode_place(place_format, country)
            if coords:
                lat, lon = coords
                print(
                    f"    [geopy] Geolocation av '{place_format}' gav (lat,lon)=({lat:.5f},{lon:.5f})"
                )
                rc = reverse_geocode_country(lat, lon)
                if rc:
                    true_country = rc
                    print(f"    [reverse_geocoder] Koordinater → land='{true_country}'")
                else:
                    print(
                        "    [reverse_geocoder] Kunde inte avgöra land från koordinater."
                    )
            else:
                print("    [geopy] Kunde inte hitta någon lat/lon för platsen.")

        # Utvärdera resultatet från pgeocode eller reverse_geocoder
        if true_country is None:
            # Både pgeocode och reverse_geocoder/ geopy misslyckades
            info["validation_uncertain"] = True
            info["last_validated"] = datetime.now(timezone.utc).isoformat()
            updated = True
            print("  [RESULTAT] Kunde inte avgöra land → validation_uncertain = true.")
            continue

        # Om vi hittade ett landkod, men det skiljer sig från det vi trodde
        if true_country.upper() != country.upper():
            info["country_found"] = False
            info["matched_neighbor"] = true_country.upper()
            info["last_validated"] = datetime.now(timezone.utc).isoformat()
            updated = True
            print(
                f"  [INVALID] '{place_format}' hör tydligen till '{true_country.upper()}', inte '{country}'."
            )
        else:
            info["country_found"] = True
            info["matched_neighbor"] = ""
            info["last_validated"] = datetime.now(timezone.utc).isoformat()
            updated = True
            print(f"  [VALID] '{place_format}' valideras som '{country}'.")

    # Om vi uppdaterat något → skriv tillbaka JSON‐filen
    if updated:
        save_db(db)
        print(f"\nValidering slutförd. Skrev uppdaterad data till {DB_FILE}.")
    else:
        print("Inga ändringar behövde göras (alla poster redan validerade).")


if __name__ == "__main__":
    validate_tertiary_hits()
