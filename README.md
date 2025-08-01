# Home Assistant: Pollen Information EU

[![GitHub Release][releases-shield]][releases]
[![License][license-shield]](LICENSE)

[![hacs][hacsbadge]][hacs]
[![Project Maintenance][maintenance-shield]][user_profile]
[![BuyMeCoffee][buymecoffeebadge]][buymecoffee]

A Home Assistant integration for monitoring pollen across Europe, data provided through [the Austrian Pollen Information Service](https://www.polleninformation.eu).

> **NOTE:** You must use your own API key. Request it [here](https://www.polleninformation.at/en/data-interface/request-an-api-key).

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

- **Supported countries:** Austria, Switzerland, Germany, Spain, France, United Kingdom, Italy, Lithuania, Latvia, Poland, Sweden, Türkiye, and Ukraine.
- **Multiple allergens:** Individual sensors for each detected allergen. *Different countries have different supported allergens.*
- **Multi-day forecast:** Each sensor exposes several days of forecast data.
- **Allergy risk**, by day and by hour.
- **Icons & friendly names:** Instantly recognizable in the Home Assistant UI.
- **Pair with pollenprognos-card:** Screenshots above have been made with [pollenprognos-card](https://github.com/krissen/pollenprognos-card)

---

## Installation (HACS recommended)

1. Search for and install **Pollen Information EU**.
3. Restart Home Assistant when prompted.

---

## Configuration

1. Go to **Settings → Devices & Services → Add Integration**.
2. Search for `Pollen Information EU` and follow the setup flow:
3. Choose a country;
4. enter a place name (free text);
5. set location through the map or by entering coordinates;
6. enter your API key.
7. Sensors will be automatically created for each available allergen at your chosen location.

---

## Usage

The integration will create sensors named like:

- `sensor.polleninformation_stockholm_birch`
- `sensor.polleninformation_stockholm_grasses`
- ...and more, depending on your location.

Each sensor includes:

 - Current pollen level as text (numeric value available in attributes)
 - Multi-day forecast as an attribute
 - Human-friendly names and icons for all entities

### Understanding the values

All allergen sensors use a scale from `0` to `4`:

| Value | Meaning     |
|------:|-------------|
| 0     | none        |
| 1     | low         |
| 2     | moderate    |
| 3     | high        |
| 4     | very high   |

The allergy risk provided by the API ranges from `0` to `10`. The
integration scales this value to the same `0`–`4` range by applying
`round(value / 2.5)` so that all sensors share a common scale.
The original `0`–`10` value is available as the `numeric_state_raw`
attribute of the `allergy_risk` sensor.

**The integration updates sensor data every 8 hours.** Which is more than enough, as the data usually does not change more frequently than once every 24 hours.

### API usage

This integration uses the official public API provided by the [Austrian Pollen Information Service](https://www.polleninformation.at/en/data-interface).
You **must request a personal API key** to use the integration—get your key [here](https://www.polleninformation.at/en/data-interface/request-an-api-key).

*For more information about the API and its terms of use, see [Austrian Pollen Information Service - Data Interface](https://www.polleninformation.at/en/data-interface).*

---

## Data Source & Attribution

All data is provided by the [Austrian Pollen Information Service](https://www.polleninformation.at/), via their [official public API](https://www.polleninformation.at/en/data-interface).  

---

[Want to support development? Buy me a coffee!](https://coff.ee/krissen)

---

[hacs]: https://hacs.xyz
[hacsbadge]: https://img.shields.io/badge/HACS-Official-orange.svg?style=for-the-badge
[license-shield]: https://img.shields.io/github/license/krissen/polleninformation.svg?style=for-the-badge
[maintenance-shield]: https://img.shields.io/badge/maintainer-%40krissen-blue.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/krissen/polleninformation.svg?style=for-the-badge
[releases]: https://github.com/krissen/polleninformation/releases
[user_profile]: https://github.com/krissen
[buymecoffee]: https://coff.ee/krissen
[buymecoffeebadge]: https://img.shields.io/badge/buy%20me%20a%20coffee-donate-yellow.svg?style=for-the-badge
