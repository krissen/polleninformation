import json
import re

with open("responses", encoding="utf-8") as f:
    content = f.read()

pattern = re.compile(
    r"^====\s+([A-Z]{2})\s+\([^)]+\)\s+====\s*\n(.*?^\})\s*(?=^====|\Z)",
    re.DOTALL | re.MULTILINE,
)

sensorless = []
total = 0
for match in pattern.finditer(content):
    code = match.group(1)
    json_text = match.group(2)
    try:
        data = json.loads(json_text)
        result = data.get("result", {})
        contamination = result.get("contamination", [])
        additional = result.get("additionalForecastData", [])
        if not contamination and not additional:
            sensorless.append(code)
        total += 1
    except Exception as e:
        print(f"Error parsing country {code}: {e}")

print(f"Länder i filen: {total}")
if sensorless:
    print("Länder utan sensorer/allergener:")
    for code in sensorless:
        print("-", code)
else:
    print("Alla länder verkar ha minst en sensor/allergen.")

