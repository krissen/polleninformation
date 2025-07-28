"""custom_components/polleninformation/const.py"""

"""Constants for polleninformation.at integration (new API version)."""

# Metadata
NAME = "PollenInformation"
VERSION = "1.0.0"
DOMAIN = "polleninformation"
ATTRIBUTION = "© Polleninformation Austria"

# Platforms
PLATFORMS = ["sensor"]

# Configuration keys (new API)
CONF_LATITUDE = "latitude"
CONF_LONGITUDE = "longitude"
CONF_COUNTRY = "country"  # ISO alpha-2, e.g. "SE"
CONF_LANG = "lang"  # ISO 639-1 language code, e.g. "sv"
CONF_APIKEY = "apikey"

# Default configuration values
DEFAULT_LATITUDE = 46.628
DEFAULT_LONGITUDE = 14.309
DEFAULT_COUNTRY = "AT"  # ISO alpha-2 country code
DEFAULT_LANG = "en"
DEFAULT_NAME = "Polleninformation"
DEFAULT_APIKEY = ""  # Empty by default; must be set by user

# API URL for polleninformation.at (new structure)
POLLENAT_API_URL = (
    "https://www.polleninformation.at/api/forecast/public"
    "?country={country}"
    "&lang={lang}"
    "&latitude={latitude}"
    "&longitude={longitude}"
    "&apikey={apikey}"
)

# Supported ISO 3166-1 alpha-2 country codes
SUPPORTED_COUNTRIES = [
    "AT",
    "CH",
    "DE",
    "ES",
    "FR",
    "GB",
    "IT",
    "LV",
    "LT",
    "PL",
    "SE",
    "TR",
    "UA",
]

# Supported ISO 639-1 language codes
SUPPORTED_LANGUAGES = [
    "de",
    "en",
    "fi",
    "sv",
    "fr",
    "it",
    "lv",
    "lt",
    "pl",
    "pt",
    "ru",
    "sk",
    "es",
    "tr",
    "uk",
    "hu",
]

# Display names for countries (can be extended or localized if needed)
COUNTRY_DISPLAY_NAMES = {
    "AT": "Austria",
    "CH": "Switzerland",
    "DE": "Germany",
    "ES": "Spain",
    "FR": "France",
    "GB": "Great Britain",
    "IT": "Italy",
    "LV": "Latvia",
    "LT": "Lithuania",
    "PL": "Poland",
    "SE": "Sweden",
    "TR": "Türkiye",
    "UA": "Ukraine",
}

# Display names for languages
LANGUAGE_DISPLAY_NAMES = {
    "de": "German",
    "en": "English",
    "fi": "Finnish",
    "sv": "Swedish",
    "fr": "French",
    "it": "Italian",
    "lv": "Latvian",
    "lt": "Lithuanian",
    "pl": "Polish",
    "pt": "Portuguese",
    "ru": "Russian",
    "sk": "Slovak",
    "es": "Spanish",
    "tr": "Turkish",
    "uk": "Ukrainian",
    "hu": "Hungarian",
}
