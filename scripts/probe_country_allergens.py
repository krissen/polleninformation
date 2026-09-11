#!/usr/bin/env python3
"""Probe the polleninformation.at API for the allergens each country reports.

For every country in SUPPORTED_COUNTRIES, call the API once in the
country's own language (falling back to English when the country's
language is not one of SUPPORTED_LANGUAGES), list the allergens (poll_id,
poll_title) returned, and flag any poll_id missing from language_map.json
for that language.

Requires POLLENAT_API_KEY environment variable.
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

import aiohttp
import async_timeout

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from custom_components.polleninformation.const import (  # noqa: E402
    SUPPORTED_COUNTRIES,
    SUPPORTED_LANGUAGES,
)

API_URL = (
    "https://www.polleninformation.at/api/forecast/public"
    "?country={country}"
    "&lang={lang}"
    "&latitude={lat}"
    "&longitude={lon}"
    "&apikey={apikey}"
)

# Coordinates from scripts/check_api_status.py's COUNTRIES table, paired
# with each country's own language (fallback resolved by _lang_for_country).
COUNTRY_INFO = {
    "AT": (48.2082, 16.3738, "de"),
    "CH": (47.3769, 8.5417, "de"),
    "DE": (52.5200, 13.4050, "de"),
    "ES": (40.4168, -3.7038, "es"),
    "FI": (60.1699, 24.9384, "fi"),
    "FR": (48.8566, 2.3522, "fr"),
    "GB": (51.5074, -0.1278, "en"),
    "HU": (47.4979, 19.0402, "hu"),
    "IT": (41.9028, 12.4964, "it"),
    "LT": (54.6872, 25.2797, "lt"),
    "LV": (56.9496, 24.1052, "lv"),
    "PL": (52.2297, 21.0122, "pl"),
    "PT": (38.7223, -9.1393, "pt"),
    "SE": (59.3293, 18.0686, "sv"),
    "SK": (48.1486, 17.1077, "sk"),
    "TR": (39.9334, 32.8597, "tr"),
    "UA": (50.4501, 30.5234, "uk"),
}

LANGUAGE_MAP_FILE = REPO_ROOT / "custom_components" / "polleninformation" / "language_map.json"


def _lang_for_country(code: str) -> str:
    _, _, lang = COUNTRY_INFO[code]
    return lang if lang in SUPPORTED_LANGUAGES else "en"


async def probe_country(session: aiohttp.ClientSession, code: str, lang: str, apikey: str) -> dict:
    lat, lon, _ = COUNTRY_INFO[code]
    url = API_URL.format(country=code, lang=lang, lat=lat, lon=lon, apikey=apikey)
    try:
        async with (
            async_timeout.timeout(15),
            session.get(url, headers={"Accept": "application/json"}) as resp,
        ):
            if resp.status != 200:
                return {"code": code, "lang": lang, "error": f"HTTP {resp.status}"}
            data = await resp.json()
    except Exception as e:  # noqa: BLE001 -- report any failure, keep probing the rest
        return {"code": code, "lang": lang, "error": str(e)}

    allergens = [
        {"poll_id": item.get("poll_id"), "poll_title": item.get("poll_title")}
        for item in data.get("contamination", [])
    ]
    return {"code": code, "lang": lang, "allergens": allergens, "raw": data}


def _known_poll_ids(language_map: dict, lang: str) -> set:
    entry = language_map.get(lang)
    if not entry:
        return set()
    return {t["poll_id"] for t in entry.get("poll_titles", [])}


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--country", help="Limit the probe to a single country code")
    parser.add_argument("--json", action="store_true", help="Dump raw API responses as JSON")
    args = parser.parse_args()

    apikey = os.environ.get("POLLENAT_API_KEY")
    if not apikey:
        print("ERROR: POLLENAT_API_KEY environment variable not set", file=sys.stderr)
        sys.exit(1)

    with LANGUAGE_MAP_FILE.open(encoding="utf-8") as f:
        language_map = json.load(f)

    countries = [args.country.upper()] if args.country else sorted(SUPPORTED_COUNTRIES)
    unknown = [c for c in countries if c not in SUPPORTED_COUNTRIES]
    if unknown:
        print(f"ERROR: unknown country code(s): {unknown}", file=sys.stderr)
        sys.exit(1)

    async with aiohttp.ClientSession() as session:
        results = await asyncio.gather(
            *(probe_country(session, code, _lang_for_country(code), apikey) for code in countries)
        )

    if args.json:
        print(json.dumps([r.get("raw", r) for r in results], indent=2))
        return

    total_missing = 0
    for r in results:
        if "error" in r:
            print(f"{r['code']} ({r['lang']}): ERROR - {r['error']}")
            continue
        known = _known_poll_ids(language_map, r["lang"])
        missing = [a for a in r["allergens"] if a["poll_id"] not in known]
        total_missing += len(missing)
        summary = ", ".join(f"{a['poll_id']}:{a['poll_title']}" for a in r["allergens"])
        print(f"{r['code']} ({r['lang']}): {len(r['allergens'])} allergen(s) - {summary}")
        for m in missing:
            print(
                f"    MISSING from language_map[{r['lang']}]: poll_id {m['poll_id']} ({m['poll_title']})"
            )

    error_count = sum(1 for r in results if "error" in r)
    print(
        f"\nSummary: {len(results)} countries probed, {error_count} error(s), {total_missing} missing poll_id(s)"
    )


if __name__ == "__main__":
    asyncio.run(main())
