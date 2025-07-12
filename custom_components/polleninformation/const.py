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
CONF_COUNTRY = "country"  # ISO alpha-2, t.ex. "SE"
CONF_COUNTRY_ID = "country_id"  # Numeriskt country-id ("C"), t.ex. 26
CONF_LANG = "lang"
CONF_LANG_ID = "lang_id"

# Standardvärden för konfiguration
DEFAULT_LATITUDE = 46.628
DEFAULT_LONGITUDE = 14.309
DEFAULT_COUNTRY = "AT"  # Landkod, ISO alpha-2
DEFAULT_COUNTRY_ID = "1"  # Numeriskt id ("C"), t.ex. 1 för Österrike
DEFAULT_NAME = "Polleninformation"
DEFAULT_LANG = "de"
DEFAULT_LANG_ID = "0"

# Parametrar som krävs enligt nya API:t
DEFAULT_ID = "0"
DEFAULT_TYPE = "15976824"
DEFAULT_L = "0"
DEFAULT_TX_ACTION = "getFullContaminationData"
DEFAULT_PERSONAL_CONTAMINATION = "false"
DEFAULT_SENSITIVITY = "0"
DEFAULT_SESSIONID = ""
DEFAULT_PASYFO = "0"

# API-url för polleninformation.at enligt ny struktur
POLLENAT_API_URL = (
    "https://www.polleninformation.at/index.php"
    "?id={id}"
    "&type={type}"
    "&lang_code={lang}"
    "&lang_id={lang_id}"
    "&L={L}"
    "&tx_scapp_appapi%5Baction%5D={tx_action}"
    "&locationType=gps"
    "&C={country_id}"
    "&personal_contamination={personal_contamination}"
    "&sensitivity={sensitivity}"
    "&country={country}"
    "&sessionid={sessionid}"
    "&pasyfo={pasyfo}"
    "&value%5Blatitude%5D={lat}"
    "&value%5Blongitude%5D={lon}"
)
