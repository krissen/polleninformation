# Troubleshooting

This guide covers the most common issues reported with the Polleninformation EU integration and how to resolve them. If your issue is not listed here, please [open a GitHub issue](https://github.com/krissen/polleninformation/issues/new/choose) with the diagnostic information described in [Collecting diagnostic information](#collecting-diagnostic-information).

## Before you report an issue

Most reported problems fall into a few well-known categories. Please work through this checklist before opening an issue:

1. **Check the API status** at the [API Status Page](https://krissen.github.io/polleninformation/) or the badge at the top of the README. If the API is down, sensors will show "unknown" state until the service is restored. This is by far the most common cause of "no sensors" reports.
2. **Verify your integration version** (see [How to find the integration version](#how-to-find-the-integration-version))
3. **Check Home Assistant logs** for errors (see [How to check Home Assistant logs](#how-to-check-home-assistant-logs))
4. **Restart Home Assistant** (see [How to restart Home Assistant](#how-to-restart-home-assistant))
5. **Check Developer Tools > States** for your sensors (see [How to check sensor states](#how-to-check-sensor-states))

If the issue persists after these steps, open an issue with the diagnostic info from the template.

---

## Common issues

### No sensors / sensors disappeared

**This is the most frequently reported issue.** In nearly all cases, the root cause is the upstream API (polleninformation.eu) being temporarily unavailable. The integration fetches data from an external server maintained by the Austrian Pollen Information Service; when that server has problems, the integration cannot create or update sensors.

**Symptoms:**
- "No pollen data returned for this location" during setup
- Sensors that previously worked now show "unknown" state
- No sensor entities appear at all

**What to do:**

1. **Check the [API Status Page](https://krissen.github.io/polleninformation/).** The status is updated twice daily (6 AM and 6 PM). If your country shows as down, the problem is server-side and will resolve when the API is restored.
2. **Wait and restart.** When the API comes back online, restart Home Assistant to trigger a fresh data fetch. Existing sensors will recover automatically once data is available again.
3. **Try a manual refresh.** Call `homeassistant.update_entity` in Developer Tools > Services, targeting one of your pollen sensors. This forces an immediate API request without restarting.
4. **If the API status shows OK but you still have no data**, check that your country, coordinates, and API key are correct in the integration configuration (Settings > Devices & Services > Polleninformation EU > Configure).

> **Note:** Not all countries have data at all times. Some countries only provide data during the pollen season. The API may return empty data outside the active season.

### Sensors unavailable after Home Assistant update

After updating Home Assistant, sensors may become "unavailable" rather than showing data.

**This was fixed in v0.4.5.** If you are running an older version, update the integration through HACS.

**If you are already on v0.4.5 or later and still see unavailable sensors:**
1. Check Home Assistant logs for errors mentioning `polleninformation`
2. Restart Home Assistant
3. If the issue persists, remove the integration and re-add it

### Configuration errors

**"No pollen data returned for this location" during initial setup:**
- Verify that the API is available (see above)
- Double-check your API key. You need a personal key from [polleninformation.at](https://www.polleninformation.at/en/data-interface/request-an-api-key)
- Ensure your coordinates are within the selected country

**Leftover configuration from an older version (pre-0.4.0):**

The integration was significantly rewritten in v0.4.0 (new API, new config flow). If you upgraded from an earlier version without removing the old configuration first, you may see errors or stale sensors (such as air quality sensors that no longer exist).

**How to fix:**
1. Go to Settings > Devices & Services
2. Find and remove the old Polleninformation EU entry
3. Restart Home Assistant
4. Add the integration again from scratch

### Country naming: "Great Britain" (not "United Kingdom")

The API uses "Great Britain" as the country name. If you set up the integration looking for "United Kingdom", it will not match. This display name was corrected in v0.4.4. Update the integration if you see the old name.

### Data not refreshing

The integration updates sensor data every 8 hours by default (configurable from 1 to 24 hours in Settings > Devices & Services > Polleninformation EU > Configure).

If data appears stale:
1. Check the `last_updated` attribute on a sensor in Developer Tools > States. This shows the actual time of the last successful API fetch.
2. Trigger a manual refresh by calling `homeassistant.update_entity` in Developer Tools > Services.
3. If neither works, check the logs for API errors.

> **Note:** In versions before v0.5.1, the `last_updated` attribute was incorrect (it showed the time you viewed the sensor, not the actual last fetch). Update to v0.5.1 or later for accurate timestamps.

### HACS download or update failures

If HACS reports a 404 error when downloading or updating, the release assets may not have been packaged correctly. Check the [releases page](https://github.com/krissen/polleninformation/releases) to see if the version you are trying to install has a `polleninformation.zip` asset attached. If not, try a different version or report the issue.

---

## Collecting diagnostic information

When reporting an issue, include the following. This information helps diagnose the problem without multiple rounds of back-and-forth questions.

### How to find the integration version

1. Go to **Settings > Devices & Services**
2. Click on the **Polleninformation EU** integration
3. Click the three-dot menu (top right of the integration card)
4. Select **About**
5. The version number is shown there

### How to check Home Assistant logs

1. Go to **Settings > System > Logs**
2. Search for `polleninformation`
3. Copy any error entries that appear

To enable debug logging for more detailed output, add this to your `configuration.yaml`:
```yaml
logger:
  default: warning
  logs:
    custom_components.polleninformation: debug
```
Restart Home Assistant after adding this. Reproduce the issue, then check the logs again.

### How to check sensor states

1. Go to **Developer Tools > States** (in HA 2026.2+: **Settings > Developer Tools > States**)
2. In the filter field, type `polleninformation`
3. This shows all sensor entities, their current state, and their attributes

Copy a few example entity IDs and their states when reporting an issue.

### How to restart Home Assistant

1. Go to **Settings > System**
2. Click the three-dot menu (top right)
3. Select **Restart Home Assistant**

---

## Is it an integration issue or something else?

Many reported issues turn out to be problems with the upstream API, not a bug in the integration itself.

| Check | Result | Likely cause |
|-------|--------|--------------|
| [API Status Page](https://krissen.github.io/polleninformation/) shows your country as down | API unavailable | **Upstream API** (wait for restoration) |
| Sensors exist in Developer Tools > States but show "unknown" | Sensor exists, no data | **Upstream API** (no data available for your location) |
| No sensor entities at all after setup | Setup completed but nothing appeared | **Integration** or **API** (check logs for errors) |
| Logs show `PollenApiAuthError` | Authentication failed | **API key** (verify or re-request your key) |
| Logs show `PollenApiConnectionError` | Cannot reach API | **Network** or **upstream API** |
| Sensors worked, then stopped after HA update | HA update broke something | **Integration** (check for a newer version) |
| Everything works in the integration but the Lovelace card shows no data | Card cannot find sensors | **Card issue** (report on the [card repository](https://github.com/krissen/pollenprognos-card)) |

If you determine the issue is with the API itself (server down, empty data for your country), there is nothing the integration can do until the service is restored. The [API Status Page](https://krissen.github.io/polleninformation/) is the best place to monitor availability.
