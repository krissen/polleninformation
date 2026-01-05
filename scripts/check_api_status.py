#!/usr/bin/env python3
"""Check polleninformation.at API status for all supported countries.

Outputs status as JSON and Markdown for GitHub Pages.
Requires POLLENAT_API_KEY environment variable.
"""

import asyncio
import json
import os
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import aiohttp
import async_timeout

API_URL = (
    "https://www.polleninformation.at/api/forecast/public"
    "?country={country}"
    "&lang=en"
    "&latitude={lat}"
    "&longitude={lon}"
    "&apikey={apikey}"
)

COUNTRIES = {
    "AT": {"name": "Austria", "lat": 48.2082, "lon": 16.3738},
    "CH": {"name": "Switzerland", "lat": 47.3769, "lon": 8.5417},
    "DE": {"name": "Germany", "lat": 52.5200, "lon": 13.4050},
    "ES": {"name": "Spain", "lat": 40.4168, "lon": -3.7038},
    "FR": {"name": "France", "lat": 48.8566, "lon": 2.3522},
    "GB": {"name": "Great Britain", "lat": 51.5074, "lon": -0.1278},
    "IT": {"name": "Italy", "lat": 41.9028, "lon": 12.4964},
    "LT": {"name": "Lithuania", "lat": 54.6872, "lon": 25.2797},
    "LV": {"name": "Latvia", "lat": 56.9496, "lon": 24.1052},
    "PL": {"name": "Poland", "lat": 52.2297, "lon": 21.0122},
    "SE": {"name": "Sweden", "lat": 59.3293, "lon": 18.0686},
    "TR": {"name": "Türkiye", "lat": 39.9334, "lon": 32.8597},
    "UA": {"name": "Ukraine", "lat": 50.4501, "lon": 30.5234},
}


@dataclass
class CountryStatus:
    code: str
    name: str
    status: str
    http_code: int | None
    allergen_count: int
    latency_ms: int | None
    error: str | None
    location: str | None


async def check_country(
    session: aiohttp.ClientSession, code: str, info: dict, apikey: str
) -> CountryStatus:
    url = API_URL.format(
        country=code,
        lat=info["lat"],
        lon=info["lon"],
        apikey=apikey,
    )

    loop = asyncio.get_running_loop()
    start = loop.time()
    try:
        async with async_timeout.timeout(15):
            async with session.get(
                url,
                headers={
                    "Accept": "application/json",
                    "User-Agent": "PollenStatusChecker/1.0",
                },
            ) as resp:
                latency = int((loop.time() - start) * 1000)
                http_code = resp.status

                if http_code == 401:
                    return CountryStatus(
                        code=code,
                        name=info["name"],
                        status="auth_error",
                        http_code=http_code,
                        allergen_count=0,
                        latency_ms=latency,
                        error="Invalid API key",
                        location=None,
                    )

                if http_code != 200:
                    return CountryStatus(
                        code=code,
                        name=info["name"],
                        status="http_error",
                        http_code=http_code,
                        allergen_count=0,
                        latency_ms=latency,
                        error=f"HTTP {http_code}",
                        location=None,
                    )

                try:
                    data = await resp.json()
                except Exception:
                    return CountryStatus(
                        code=code,
                        name=info["name"],
                        status="parse_error",
                        http_code=http_code,
                        allergen_count=0,
                        latency_ms=latency,
                        error="Invalid JSON response",
                        location=None,
                    )

                if "error" in data:
                    return CountryStatus(
                        code=code,
                        name=info["name"],
                        status="api_error",
                        http_code=http_code,
                        allergen_count=0,
                        latency_ms=latency,
                        error=data.get("error"),
                        location=None,
                    )

                contamination = data.get("contamination", [])
                allergen_count = len(contamination)
                location = data.get("locationtitle")

                if allergen_count == 0:
                    status = "empty"
                else:
                    status = "ok"

                return CountryStatus(
                    code=code,
                    name=info["name"],
                    status=status,
                    http_code=http_code,
                    allergen_count=allergen_count,
                    latency_ms=latency,
                    error=None,
                    location=location,
                )

    except asyncio.TimeoutError:
        return CountryStatus(
            code=code,
            name=info["name"],
            status="timeout",
            http_code=None,
            allergen_count=0,
            latency_ms=None,
            error="Request timed out",
            location=None,
        )
    except Exception as e:
        return CountryStatus(
            code=code,
            name=info["name"],
            status="connection_error",
            http_code=None,
            allergen_count=0,
            latency_ms=None,
            error=str(e),
            location=None,
        )


def status_emoji(status: str) -> str:
    return {
        "ok": "✅",
        "empty": "⚠️",
        "timeout": "🕐",
        "auth_error": "🔑",
        "http_error": "❌",
        "api_error": "❌",
        "parse_error": "❌",
        "connection_error": "🔌",
    }.get(status, "❓")


def generate_markdown(results: list[CountryStatus], timestamp: str) -> str:
    lines = [
        "# Pollen API Status",
        "",
        f"Last updated: **{timestamp}** UTC",
        "",
        "| Country | Status | Allergens | Latency | Location |",
        "|---------|--------|-----------|---------|----------|",
    ]

    for r in sorted(results, key=lambda x: x.code):
        emoji = status_emoji(r.status)
        latency = f"{r.latency_ms}ms" if r.latency_ms else "-"
        allergens = str(r.allergen_count) if r.allergen_count else "-"
        location = r.location or "-"
        if r.error and r.status != "ok":
            location = f"_{r.error}_"

        lines.append(
            f"| {r.name} ({r.code}) | {emoji} {r.status} | {allergens} | {latency} | {location} |"
        )

    lines.extend(
        [
            "",
            "## Legend",
            "",
            "| Symbol | Meaning |",
            "|--------|---------|",
            "| ✅ ok | API returned valid data with allergens |",
            "| ⚠️ empty | API returned valid response but no allergen data |",
            "| 🕐 timeout | Request timed out |",
            "| 🔑 auth_error | API key invalid or unauthorized |",
            "| ❌ http_error / api_error | Server returned an error |",
            "| 🔌 connection_error | Could not connect to server |",
            "",
            "---",
            "",
            "*This page is automatically updated twice daily by GitHub Actions.*",
        ]
    )

    return "\n".join(lines)


async def main():
    apikey = os.environ.get("POLLENAT_API_KEY")
    if not apikey:
        print("ERROR: POLLENAT_API_KEY environment variable not set", file=sys.stderr)
        sys.exit(1)

    output_dir = Path(__file__).parent.parent / "docs"
    output_dir.mkdir(exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    async with aiohttp.ClientSession() as session:
        tasks = [
            check_country(session, code, info, apikey)
            for code, info in COUNTRIES.items()
        ]
        results = await asyncio.gather(*tasks)

    json_data = {
        "timestamp": timestamp,
        "countries": [asdict(r) for r in results],
    }

    json_path = output_dir / "status.json"
    json_path.write_text(json.dumps(json_data, indent=2))

    md_content = generate_markdown(results, timestamp)
    md_path = output_dir / "index.md"
    md_path.write_text(md_content)

    print(f"Status check complete at {timestamp}")
    print(f"  JSON: {json_path}")
    print(f"  Markdown: {md_path}")

    ok_count = sum(1 for r in results if r.status == "ok")
    empty_count = sum(1 for r in results if r.status == "empty")
    error_count = len(results) - ok_count - empty_count

    print(f"  Results: {ok_count} OK, {empty_count} empty, {error_count} errors")

    if error_count > 0:
        for r in results:
            if r.status not in ("ok", "empty"):
                print(f"    {r.code}: {r.status} - {r.error}")


if __name__ == "__main__":
    asyncio.run(main())
