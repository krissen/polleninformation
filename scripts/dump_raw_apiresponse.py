#!/usr/bin/env python3
import asyncio
import json

import aiohttp
import async_timeout

# 1. Läs in available_countries.json
with open(
    "custom_components/polleninformation/available_countries.json", encoding="utf-8"
) as f:
    countries = json.load(f)["countries"]

# 2. Lista över huvudstäder och default lat/lon (du kan lägga in fler om du vill)
CAPITALS = {
    "AT": (48.2082, 16.3738),  # Vienna
    "BE": (50.8503, 4.3517),  # Brussels
    "BG": (42.6977, 23.3219),  # Sofia
    "CH": (
        47.3769,
        8.5417,
    ),  # Zurich (de facto economic capital, Bern: 46.9480, 7.4474)
    "CZ": (50.0755, 14.4378),  # Prague
    "DE": (52.5200, 13.4050),  # Berlin
    "DK": (55.6761, 12.5683),  # Copenhagen
    "EE": (59.4369, 24.7535),  # Tallinn
    "ES": (40.4168, -3.7038),  # Madrid
    "FR": (48.8566, 2.3522),  # Paris
    "GB": (51.5074, -0.1278),  # London
    "FI": (60.1699, 24.9384),  # Helsinki
    "GR": (37.9838, 23.7275),  # Athens
    "HR": (45.8150, 15.9819),  # Zagreb
    "HU": (47.4979, 19.0402),  # Budapest
    "IE": (53.3498, -6.2603),  # Dublin
    "IT": (41.9028, 12.4964),  # Rome
    "LT": (54.6872, 25.2797),  # Vilnius
    "LU": (49.6116, 6.1319),  # Luxembourg
    "LV": (56.9496, 24.1052),  # Riga
    "MT": (35.8989, 14.5146),  # Valletta
    "NL": (52.3676, 4.9041),  # Amsterdam
    "NO": (59.9139, 10.7522),  # Oslo
    "PL": (52.2297, 21.0122),  # Warsaw
    "PT": (38.7223, -9.1393),  # Lisbon
    "RO": (44.4268, 26.1025),  # Bucharest
    "SE": (59.3293, 18.0686),  # Stockholm
    "SI": (46.0569, 14.5058),  # Ljubljana
    "SK": (48.1486, 17.1077),  # Bratislava
    "TR": (39.9334, 32.8597),  # Ankara
    "UA": (50.4501, 30.5234),  # Kyiv
    "AL": (41.3275, 19.8187),  # Tirana
    "AD": (42.5063, 1.5218),  # Andorra la Vella
    "BA": (43.8563, 18.4131),  # Sarajevo
    "BY": (53.9006, 27.5590),  # Minsk
    "LI": (47.1660, 9.5554),  # Vaduz
    "MK": (41.6086, 21.7453),  # Skopje
    "MD": (47.0105, 28.8638),  # Chişinău
    "MC": (43.7384, 7.4246),  # Monaco
    "ME": (42.4304, 19.2594),  # Podgorica
    "SM": (43.9354, 12.4475),  # San Marino
    "VA": (41.9029, 12.4534),  # Vatican City
}

POLLENAT_API_URL = (
    "https://www.polleninformation.at/index.php"
    "?eID=appinterface"
    "&pure_json=1"
    "&lang_code=de"
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


async def fetch_raw(country, lat, lon, country_id):
    url = POLLENAT_API_URL.format(
        lat=lat, lon=lon, country=country, country_id=country_id
    )
    async with async_timeout.timeout(15):
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                text = await resp.text()
                try:
                    return json.loads(text)
                except Exception:
                    return text


async def main():
    for country in countries:
        code = country["code"]
        country_id = (
            country["country_id"][0]
            if isinstance(country["country_id"], list)
            else country["country_id"]
        )
        lat, lon = CAPITALS.get(
            code, (59.3293, 18.0686)
        )  # default to Stockholm if missing
        print(f"\n==== {code} ({country['name']}) ====")
        raw = await fetch_raw(code, lat, lon, country_id)
        print(json.dumps(raw, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
