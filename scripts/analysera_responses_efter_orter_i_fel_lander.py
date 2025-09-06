import json
import re
import pandas as pd
import pgeocode
import requests

# Dämpar specifik FutureWarning för fillna
pd.set_option("future.no_silent_downcasting", True)

EU_COUNTRIES = [
    "AT",
    "BE",
    "BG",
    "CH",
    "CZ",
    "DE",
    "DK",
    "EE",
    "ES",
    "FI",
    "FR",
    "GB",
    "GR",
    "HR",
    "HU",
    "IE",
    "IT",
    "LT",
    "LU",
    "LV",
    "MT",
    "NL",
    "NO",
    "PL",
    "PT",
    "RO",
    "SE",
    "SI",
    "SK",
]
RESPONSES_FILE = "responses"


def get_country_code_from_gps(lat, lon):
    url = "https://nominatim.openstreetmap.org/reverse"
    params = {"lat": lat, "lon": lon, "zoom": 3, "format": "json", "addressdetails": 1}
    headers = {"User-Agent": "Polleninformation-Validation/1.2"}
    try:
        r = requests.get(url, params=params, headers=headers, timeout=10)
        if r.status_code == 200:
            address = r.json().get("address", {})
            cc = address.get("country_code", "").upper()
            country_name = address.get("country", "")
            return cc, country_name
    except Exception as e:
        return None, str(e)
    return None, None


def parse_gps(value):
    if not value or "," not in value:
        return None, None
    parts = value.split(",")
    try:
        lat = float(parts[0].strip())
        lon = float(parts[1].strip())
        return lat, lon
    except Exception:
        return None, None


def color(code, text):
    codes = {
        "GRÖNT": "\033[92m",
        "ORANGE": "\033[93m",
        "RÖTT": "\033[91m",
        "SLUT": "\033[0m",
    }
    return f"{codes.get(code, '')}{text}{codes['SLUT']}"


def safe_query_postal_code(nomi, postcode):
    try:
        # Inga regex-grupper; ingen varning
        if postcode:
            return nomi.query_postal_code(re.escape(postcode))
    except Exception:
        pass
    return None


def safe_query_city(nomi, city):
    try:
        if city:
            return nomi.query_location(re.escape(city))
    except Exception:
        pass
    return None


def match_city_or_postcode(country_code, locationtitle):
    # Postcode och stad (kan vara tom)
    parts = locationtitle.strip().split(maxsplit=1)
    postcode = parts[0] if len(parts) > 1 else ""
    city = parts[1] if len(parts) > 1 else ""
    ort_info = "?"
    ort_match = False
    ort_wrong_country = False

    try:
        nomi = pgeocode.Nominatim(country_code)
        # Först, exakt postnummer-match mot blockets land
        result_pc = safe_query_postal_code(nomi, postcode)
        if result_pc is not None and isinstance(result_pc.country_code, str):
            postcode_country_code = result_pc.country_code.upper()
            ortname = getattr(result_pc, "place_name", city)
            ort_info = f"{ortname} [{postcode_country_code}]"
            ort_match = postcode_country_code == country_code
            ort_wrong_country = not ort_match and (postcode_country_code is not None)
            return ort_match, ort_wrong_country, ort_info
        # Om ingen postnummer, testa city som fallback
        locations = safe_query_city(nomi, city)
        if (
            locations is not None
            and hasattr(locations, "country_code")
            and len(locations) > 0
        ):
            loc_country_code = locations.iloc[0].country_code.upper()
            place = locations.iloc[0].place_name
            ort_info = f"{place} [{loc_country_code}] (city fallback)"
            ort_match = loc_country_code == country_code
            ort_wrong_country = not ort_match and (loc_country_code is not None)
            return ort_match, ort_wrong_country, ort_info
    except Exception as e:
        ort_info = f"fel: {e}"

    # Fallback: sök bland övriga EU-länder
    for fallback_country in EU_COUNTRIES:
        if fallback_country == country_code:
            continue
        try:
            nomi_fb = pgeocode.Nominatim(fallback_country)
            result_fb = safe_query_postal_code(nomi_fb, postcode)
            if result_fb is not None and isinstance(result_fb.country_code, str):
                postcode_country_code = result_fb.country_code.upper()
                ortname = getattr(result_fb, "place_name", city)
                ort_info = f"{ortname} [{postcode_country_code}] via {fallback_country}"
                ort_match = postcode_country_code == country_code
                ort_wrong_country = not ort_match
                return ort_match, ort_wrong_country, ort_info
            locations_fb = safe_query_city(nomi_fb, city)
            if (
                locations_fb is not None
                and hasattr(locations_fb, "country_code")
                and len(locations_fb) > 0
            ):
                loc_country_code = locations_fb.iloc[0].country_code.upper()
                place = locations_fb.iloc[0].place_name
                ort_info = f"{place} [{loc_country_code}] via {fallback_country} (city fallback)"
                ort_match = loc_country_code == country_code
                ort_wrong_country = not ort_match
                return ort_match, ort_wrong_country, ort_info
        except Exception:
            continue
    return False, False, "?"


pattern = re.compile(
    r"^====\s+([A-Z]{2})\s+\([^)]+\)\s+====\s*\n(.*?^\})\s*(?=^====|\Z)",
    re.DOTALL | re.MULTILINE,
)

with open(RESPONSES_FILE, encoding="utf-8") as f:
    content = f.read()

for match in pattern.finditer(content):
    country_code = match.group(1)
    json_str = match.group(2).strip()
    try:
        resp = json.loads(json_str)
        result = resp.get("result", {})
        locationtitle = result.get("locationtitle", "")
        gps_value = result.get("value", "")
        lat, lon = parse_gps(gps_value)

        # GPS-land
        gps_country_code, gps_country_name = None, None
        if lat is not None and lon is not None:
            gps_country_code, gps_country_name = get_country_code_from_gps(lat, lon)
        gps_match = gps_country_code == country_code
        gps_info = (
            f"{gps_country_name} [{gps_country_code}]" if gps_country_name else "?"
        )

        # Ort/postnummer-match
        ort_match, ort_wrong_country, ort_info = match_city_or_postcode(
            country_code, locationtitle
        )

        # Färglogik
        if gps_match and ort_match:
            status = color("GRÖNT", "JA")
        elif ort_wrong_country:
            status = color("RÖTT", "NEJ")
        else:
            status = color("ORANGE", "KANSKE")

        print(
            f"{country_code}: {status}  Ort: '{locationtitle}'  GPS→{gps_info}  GPS-match: {gps_match}  Ort-match: {ort_match} ({ort_info})"
        )

    except Exception as e:
        print(f"Error parsing country {country_code}: {e}")
