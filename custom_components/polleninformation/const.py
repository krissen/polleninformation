# custom_components/polleninformation/const.py
"""Konstanter för polleninformation.at-integration."""

# Metadata
NAME = "PollenInformation"
VERSION = "1.0.0"
DOMAIN = "polleninformation"
ATTRIBUTION = "© Polleninformation Austria"

# Plattformar
PLATFORMS = ["sensor"]

# Konfiguratonsnycklar
CONF_LATITUDE = "latitude"
CONF_LONGITUDE = "longitude"
CONF_COUNTRY = "country"
CONF_LANGUAGE = "language"

# Standardvärden för konfiguration
DEFAULT_LATITUDE = 46.628
DEFAULT_LONGITUDE = 14.309
DEFAULT_COUNTRY = "AT"
DEFAULT_LANGUAGE = "en"

# URL-template för polleninformation.at
POLLENAT_API_URL = (
    "https://www.polleninformation.at/index.php"
    "?eID=appinterface"
    "&pure_json=1"
    "&lang_code={lang}"
    "&lang_id=0"
    "&action=getFullContaminationData"
    "&type=gps"
    "&value[latitude]={lat}"
    "&value[longitude]={lon}"
    "&country_id=1"
    "&personal_contamination=false"
    "&sensitivity=0"
    "&country={country}"
)
