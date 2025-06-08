"""Konstanter för polleninformation.at-integration."""

# Metadata
NAME = "PollenInformation"
VERSION = "1.0.0"
DOMAIN = "polleninformation"
ATTRIBUTION = "© Polleninformation Austria"

# Plattformar
PLATFORMS = ["sensor"]

# Konfigurationsnycklar
CONF_LATITUDE = "latitude"
CONF_LONGITUDE = "longitude"
CONF_COUNTRY = "country"
CONF_COUNTRY_ID = "country_id"
CONF_LANG = "lang"
CONF_LANG_ID = "lang_id"

# Standardvärden för konfiguration
DEFAULT_LATITUDE = 46.628
DEFAULT_LONGITUDE = 14.309
DEFAULT_COUNTRY = "AT"
DEFAULT_NAME = "Polleninformation"
DEFAULT_LANG = "de"
DEFAULT_LANG_ID = 0

# URL-template för polleninformation.at
POLLENAT_API_URL = (
    "https://www.polleninformation.at/index.php"
    "?eID=appinterface"
    "&pure_json=1"
    "&lang_code={lang}"
    "&lang_id={lang_id}"
    "&action=getFullContaminationData"
    "&type=gps"
    "&value[latitude]={lat}"
    "&value[longitude]={lon}"
    "&country_id={country_id}"
    "&personal_contamination=false"
    "&sensitivity=0"
    "&country={country}"
    "&sessionid="
)
