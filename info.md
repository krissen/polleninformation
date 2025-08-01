# Home Assistant: Pollen Information EU

Pollen Information EU is a Home Assistant integration that provides up-to-date pollen data for any location in Europe, powered by the Austrian Pollen Information Service.

## Features

- **Multiple allergens**: Automatically creates a sensor for each detected allergen at your chosen location.
- **Forecast included**: Each sensor exposes a multi-day forecast as an attribute.
- **Works in multiple European countries**: Choose location by country, and latitude and longitude.

## Installation (Recommended: HACS)

1. Add this repository as a "Custom Repository" under "Integrations" in HACS.
2. Install the "Pollen Information EU" integration.
3. Restart Home Assistant if prompted.

## Configuration

1. Go to **Settings → Devices & Services → Add Integration**.
2. Search for `Pollen Information EU` and add the integration.
3. Select your country and enter your desired location (latitude/longitude).
4. Sensors will be created automatically for all available allergens at the selected location.

## Sensor Attributes

Each sensor exposes attributes such as:

- **level_en**: Current state as text (`none`, `low`, `moderate`, etc.)
- **forecast**: Array with daily forecast (each entry includes date, numeric and named level)
- **named_state / numeric_state**: Today's level (text and numeric)
- **location_title / location_slug / location_zip**: Location information
- **name_en / name_de / name_la**: Allergen name (English, German, Latin)
- **Icon**: Mapped to allergen type

### Understanding the values

All allergen sensors report values from **0** (none) to **4** (very high).
The allergy risk returned by the API uses a **0–10** scale. The integration
converts this to the same **0–4** range using `round(value / 2.5)` so that
all values are comparable.
The original `0`–`10` value can be found in the `numeric_state_raw` attribute
of the `allergy_risk` sensor.

## Data Source & Attribution

All data is provided by the Austrian Pollen Information Service.  
For more details, visit [polleninformation.at](https://www.polleninformation.at/).

---
