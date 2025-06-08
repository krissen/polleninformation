# Home Assistant: Pollen Information EU

Pollen Information EU is a Home Assistant integration that provides up-to-date pollen and air quality data for any location in Europe, powered by the Austrian Pollen Information Service.

## Features

- **Multiple allergens**: Automatically creates a sensor for each detected allergen at your chosen location.
- **Air quality sensors**: Additional sensors for ozone, particulate matter, nitrogen dioxide, sulphur dioxide, temperature, and more.
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
4. Sensors will be created automatically for all available allergens and air quality metrics at the selected location.

## Sensor Attributes

Each sensor exposes attributes such as:

- **level_en**: Current state as text (`none`, `low`, `moderate`, etc.)
- **forecast**: Array with daily forecast (each entry includes date, numeric and named level)
- **named_state / numeric_state**: Today's level (text and numeric)
- **location_title / location_slug / location_zip**: Location information
- **name_en / name_de / name_la**: Allergen name (English, German, Latin)
- **Icon**: Mapped to allergen or air quality type

## Data Source & Attribution

All data is provided by the Austrian Pollen Information Service.  
For more details, visit [polleninformation.at](https://www.polleninformation.at/).

---
