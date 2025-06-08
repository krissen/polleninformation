import json
import re

RESPONSES_FILE = "responses"

all_allergens = set()
all_air_keys = set()
countries = set()

with open(RESPONSES_FILE, encoding="utf-8") as f:
    content = f.read()

# Hitta block: ==== XX (Country) ==== följt av JSON
pattern = re.compile(
    r"^====\s+([A-Z]{2})\s+\([^)]+\)\s+====\s*\n(.*?^\})\s*(?=^====|\Z)",
    re.DOTALL | re.MULTILINE,
)

for match in pattern.finditer(content):
    country_code = match.group(1)
    countries.add(country_code)
    json_str = match.group(2)
    try:
        # Strippa extra whitespace
        json_str = json_str.strip()
        resp = json.loads(json_str)
        result = resp.get("result", {})
        # Allergener
        for item in result.get("contamination", []):
            title = item.get("poll_title")
            if title:
                all_allergens.add(title)
        # Luftkvalitet
        for day in result.get("additionalForecastData", []):
            for k in day:
                if k not in ("date", "dayrisk_personalized"):
                    all_air_keys.add(k)
    except Exception as e:
        print(f"Error parsing country {country_code}: {e}")

print(f"Länder som hittades ({len(countries)}): {', '.join(sorted(countries))}\n")

print("Unika allergener:")
for allergen in sorted(all_allergens):
    print(f"- {allergen}")

print("\nUnika luftkvalitetsfält:")
for air in sorted(all_air_keys):
    print(f"- {air}")
