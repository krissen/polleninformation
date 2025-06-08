# Home Assistant: Pollen Information EU

[![GitHub Release][releases-shield]][releases]
[![License][license-shield]](LICENSE)

[![hacs][hacsbadge]][hacs]
[![Project Maintenance][maintenance-shield]][user_profile]
[![BuyMeCoffee][buymecoffeebadge]][buymecoffee]

A modern Home Assistant integration for monitoring pollen and air quality across Europe, powered by the Austrian Pollen Information Service.

---

## Features

- **Supported countries:**  Albania, Andorra, Austria, Belarus, Belgium, Bosnia and Herzegovina, Bulgaria, Croatia, Czechia, Denmark, Estonia, Finland, France, Germany, Greece, Holy See (Vatican City State), Hungary, Ireland, Italy, Latvia, Liechtenstein, Lithuania, Luxembourg, Malta, Moldova, Republic of, Monaco, Montenegro, Netherlands, North Macedonia, Norway, Poland, Portugal, Romania, San Marino, Slovakia, Slovenia, Spain, Sweden, Switzerland, Türkiye, Ukraine, United Kingdom
- **Multiple allergens:** Individual sensors for each detected allergen.
- **Air quality:** Additional sensors for ozone, particulate matter, nitrogen dioxide, sulphur dioxide, temperature, and more.
- **Multi-day forecast:** Each sensor exposes several days of forecast data.
- **Beautiful icons & friendly names:** Instantly recognizable in the Home Assistant UI.
- **Ready for Lovelace cards:** Fully compatible with the most popular pollen and air quality cards.

---

## Installation (HACS recommended)

1. Add `https://github.com/krissen/polleninformation` as a "Custom Repository" under "Integrations" in HACS.
2. Search for and install **Pollen Information EU**.
3. Restart Home Assistant if prompted.

---

## Configuration

1. Go to **Settings → Devices & Services → Add Integration**.
2. Search for `Pollen Information EU` and follow the setup flow.
3. Enter your location (latitude/longitude) and country.
4. Sensors will be automatically created for each available allergen and air quality metric at your chosen location.

---

## Usage

The integration will create sensors named like:

- `sensor.polleninformation_stockholm_birch`
- `sensor.polleninformation_stockholm_ozone`
- ...and more, depending on your location.

Each sensor includes:

- Current pollen or air quality level
- Multi-day forecast as an attribute
- Human-friendly names and icons for all entities

---

## Data Source & Attribution

All data is provided by the [Austrian Pollen Information Service](https://www.polleninformation.at/).

---

[Want to support development? Buy me a coffee!](https://coff.ee/krissen)

---

[hacs]: https://hacs.xyz
[hacsbadge]: https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge
[license-shield]: https://img.shields.io/github/license/krissen/polleninformation.svg?style=for-the-badge
[maintenance-shield]: https://img.shields.io/badge/maintainer-%40krissen-blue.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/krissen/polleninformation.svg?style=for-the-badge
[releases]: https://github.com/krissen/polleninformation/releases
[user_profile]: https://github.com/krissen
[buymecoffee]: https://coff.ee/krissen
[buymecoffeebadge]: https://img.shields.io/badge/buy%20me%20a%20coffee-donate-yellow.svg?style=for-the-badge
