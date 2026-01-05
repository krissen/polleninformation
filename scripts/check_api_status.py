#!/usr/bin/env python3
"""Check polleninformation.at API status for all supported countries.

Outputs status as JSON and HTML for GitHub Pages.
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
    "AT": {"name": "Austria", "lat": 48.2082, "lon": 16.3738, "city": "Vienna"},
    "CH": {"name": "Switzerland", "lat": 47.3769, "lon": 8.5417, "city": "Zürich"},
    "DE": {"name": "Germany", "lat": 52.5200, "lon": 13.4050, "city": "Berlin"},
    "ES": {"name": "Spain", "lat": 40.4168, "lon": -3.7038, "city": "Madrid"},
    "FR": {"name": "France", "lat": 48.8566, "lon": 2.3522, "city": "Paris"},
    "GB": {"name": "Great Britain", "lat": 51.5074, "lon": -0.1278, "city": "London"},
    "IT": {"name": "Italy", "lat": 41.9028, "lon": 12.4964, "city": "Rome"},
    "LT": {"name": "Lithuania", "lat": 54.6872, "lon": 25.2797, "city": "Vilnius"},
    "LV": {"name": "Latvia", "lat": 56.9496, "lon": 24.1052, "city": "Riga"},
    "PL": {"name": "Poland", "lat": 52.2297, "lon": 21.0122, "city": "Warsaw"},
    "SE": {"name": "Sweden", "lat": 59.3293, "lon": 18.0686, "city": "Stockholm"},
    "TR": {"name": "Türkiye", "lat": 39.9334, "lon": 32.8597, "city": "Ankara"},
    "UA": {"name": "Ukraine", "lat": 50.4501, "lon": 30.5234, "city": "Kyiv"},
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
    test_city: str


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
                        test_city=info["city"],
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
                        test_city=info["city"],
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
                        test_city=info["city"],
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
                        test_city=info["city"],
                    )

                contamination = data.get("contamination", [])
                allergen_count = len(contamination)

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
                    test_city=info["city"],
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
            test_city=info["city"],
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
            test_city=info["city"],
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


def generate_html(results: list[CountryStatus], timestamp: str) -> str:
    rows = []
    for r in sorted(results, key=lambda x: x.code):
        emoji = status_emoji(r.status)
        latency = f"{r.latency_ms}ms" if r.latency_ms else "-"
        allergens = str(r.allergen_count) if r.allergen_count else "-"
        rows.append(
            f"<tr><td>{r.name} ({r.code})</td><td>{emoji} {r.status}</td>"
            f"<td>{allergens}</td><td>{latency}</td><td>{r.test_city}</td></tr>"
        )

    table_rows = "\n".join(rows)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Polleninformation.at API Status</title>
    <style>
        :root {{
            --bg: #fff;
            --text: #333;
            --text-muted: #666;
            --border: #ddd;
            --table-header: #f5f5f5;
            --table-hover: #f9f9f9;
            --note-bg: #fffbea;
            --note-border: #f0c000;
        }}
        @media (prefers-color-scheme: dark) {{
            :root {{
                --bg: #1a1a1a;
                --text: #e0e0e0;
                --text-muted: #999;
                --border: #444;
                --table-header: #2a2a2a;
                --table-hover: #252525;
                --note-bg: #2a2500;
                --note-border: #806000;
            }}
        }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; background: var(--bg); color: var(--text); }}
        h1 {{ color: var(--text); }}
        table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
        th, td {{ border: 1px solid var(--border); padding: 8px 12px; text-align: left; }}
        th {{ background: var(--table-header); }}
        tr:hover {{ background: var(--table-hover); }}
        .badge {{ margin: 10px 0; }}
        .footer {{ color: var(--text-muted); font-size: 0.9em; margin-top: 30px; padding-top: 20px; border-top: 1px solid var(--border); }}
        .note {{ background: var(--note-bg); border-left: 4px solid var(--note-border); padding: 10px; margin: 20px 0; }}
    </style>
</head>
<body>
    <header style="display: flex; align-items: center; gap: 15px; margin-bottom: 20px;">
        <img src="https://www.polleninformation.at/typo3conf/ext/sc_template/Resources/Public/Images/logo_polleninformation.svg" alt="Polleninformation Logo" style="height: 50px;">
        <h1 style="margin: 0;">API Status</h1>
    </header>
    <div class="badge">
        <img src="https://img.shields.io/endpoint?url=https://krissen.github.io/polleninformation/badge.json" alt="API Status">
    </div>
    <p>Last updated: <strong>{timestamp}</strong> UTC</p>

    <table>
        <thead>
            <tr><th>Country</th><th>Status</th><th>Allergens</th><th>Latency</th><th>Test Location</th></tr>
        </thead>
        <tbody>
{table_rows}
        </tbody>
    </table>

    <h2>Legend</h2>
    <table>
        <tr><td>✅ ok</td><td>API returned valid data with allergens</td></tr>
        <tr><td>⚠️ empty</td><td>API returned valid response but no allergen data</td></tr>
        <tr><td>🕐 timeout</td><td>Request timed out</td></tr>
        <tr><td>🔑 auth_error</td><td>API key invalid or unauthorized</td></tr>
        <tr><td>❌ http_error / api_error</td><td>Server returned an error</td></tr>
        <tr><td>🔌 connection_error</td><td>Could not connect to server</td></tr>
    </table>

    <div class="footer">
        <p>Automatically updated at 06:00 and 18:00 UTC by GitHub Actions.</p>
        <p class="note"><strong>Note:</strong> Status is checked using a single coordinate per country (typically the capital). Regional availability may vary.</p>
    </div>
</body>
</html>"""


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

    html_content = generate_html(results, timestamp)
    html_path = output_dir / "index.html"
    html_path.write_text(html_content)

    ok_count = sum(1 for r in results if r.status == "ok")
    empty_count = sum(1 for r in results if r.status == "empty")
    error_count = sum(1 for r in results if r.status not in ("ok", "empty"))

    if error_count > 0:
        badge_color = "red"
        badge_message = "1 error" if error_count == 1 else f"{error_count} errors"
    elif empty_count > 0:
        badge_color = "yellow"
        badge_message = f"{ok_count} OK, {empty_count} empty"
    else:
        badge_color = "brightgreen"
        badge_message = "all OK"

    badge_data = {
        "schemaVersion": 1,
        "label": "API Status",
        "message": badge_message,
        "color": badge_color,
    }
    badge_path = output_dir / "badge.json"
    badge_path.write_text(json.dumps(badge_data, indent=2))

    print(f"Status check complete at {timestamp}")
    print(f"  JSON: {json_path}")
    print(f"  HTML: {html_path}")
    print(f"  Badge: {badge_path}")
    print(f"  Results: {ok_count} OK, {empty_count} empty, {error_count} errors")

    if error_count > 0:
        for r in results:
            if r.status not in ("ok", "empty"):
                print(f"    {r.code}: {r.status} - {r.error}")


if __name__ == "__main__":
    asyncio.run(main())
