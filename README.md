# Home Assistant: Pollen Information EU

[![GitHub Release][releases-shield]][releases]
[![License][license-shield]](LICENSE)

[![hacs][hacsbadge]][hacs]
[![Project Maintenance][maintenance-shield]][user_profile]
[![BuyMeCoffee][buymecoffeebadge]][buymecoffee]

A modern Home Assistant integration for monitoring pollen and air quality across Europe, data provided through [the Austrian Pollen Information Service](https://www.polleninformation.eu).

<table align="center">
  <tr>
    <td><img width="450" alt="Skärmavbild 2025-06-09 kl  20 11 48" src="https://github.com/user-attachments/assets/e3d0815b-ea1a-4366-a3b6-3098ee26ad06" />
</td>
    <td align="center" valign="middle">
      <img width="450" alt="Skärmavbild 2025-06-09 kl  20 24 24" src="https://github.com/user-attachments/assets/0d183dd9-42d1-4dbb-ae14-b8cd5d8a544c" />
    </td>
  </tr>
  <tr>
    <td align="center" valign="middle">
      <img width="450" alt="Skärmavbild 2025-06-09 kl  20 10 46" src="https://github.com/user-attachments/assets/9385ba7a-57d8-434a-89ce-9e03892afce3" />
    </td>
    <td align="center" valign="middle">
      <img width="450" alt="Skärmavbild 2025-06-09 kl  20 10 26" src="https://github.com/user-attachments/assets/3ecfcc60-4c91-4164-b175-e3ed151ee566" />
    </td>
  </tr>
</table>

---

## Features

- **Supported countries:** Austria, Switzerland, Germany, Spain, France, United Kingdom, Italy, Lithuania, Latvia, Poland, Sweden, Türkiye, Ukraine, Holy See (Vatican City State)
- **Multiple allergens:** Individual sensors for each detected allergen. *Different countries have different supported allergens.*
- **Air quality:** Additional sensors for ozone, particulate matter, nitrogen dioxide, sulphur dioxide, temperature, and more. *Different countries have different supported air quality sensors.*
- **Multi-day forecast:** Each sensor exposes several days of forecast data.
- **Beautiful icons & friendly names:** Instantly recognizable in the Home Assistant UI.
- **Pair with pollenprognos-card:** Screenshots above have been made with [pollenprognos-card](https://github.com/krissen/pollenprognos-card)

---

## Installation (HACS recommended)

1. Add `https://github.com/krissen/polleninformation` as a "Custom Repository" as an "Integration" in HACS.
2. Search for and install **Pollen Information EU**.
3. Restart Home Assistant when prompted.

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

**The integration updates sensor data every 8 hours.** On the one hand, this could have been user configurable. On the other, we are using undocumented API and I doubt the pollen situation changes drastically within 8 hours. Better be conservative and keep using the API.

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
