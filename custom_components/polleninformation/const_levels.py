# custom_components/polleninformation/const_levels.py

# All keys are now ISO 639-1 language codes (strings)
LEVELS = {
    "de": ["keine Belastung", "gering", "mäßig", "hoch", "sehr hoch"],  # German
    "en": ["none", "low", "moderate", "high", "very high"],  # English
    "fi": [
        "ei esiintymää",
        "vähäinen",
        "kohtalainen",
        "korkea",
        "erittäin korkea",
    ],  # Finnish
    "sv": ["ingen", "låg", "måttlig", "hög", "mycket hög"],  # Swedish
    "fr": ["aucune", "faible", "modérée", "élevée", "très élevée"],  # French
    "it": ["nessuna", "bassa", "moderata", "alta", "molto alta"],  # Italian
    "lv": ["nav", "zems", "mērens", "augsts", "ļoti augsts"],  # Latvian
    "lt": ["nėra", "maža", "vidutinė", "didelė", "labai didelė"],  # Lithuanian
    "pl": ["brak", "niski", "umiarkowany", "wysoki", "bardzo wysoki"],  # Polish
    "pt": ["nenhum", "baixo", "moderado", "alto", "muito alto"],  # Portuguese
    "ru": ["нет", "низкий", "умеренный", "высокий", "очень высокий"],  # Russian
    "sk": ["žiadny", "nízky", "mierny", "vysoký", "veľmi vysoký"],  # Slovak
    "es": ["ninguno", "bajo", "moderado", "alto", "muy alto"],  # Spanish
    "tr": ["yok", "düşük", "orta", "yüksek", "çok yüksek"],  # Turkish
    "uk": ["немає", "низький", "помірний", "високий", "дуже високий"],  # Ukrainian
    "hu": ["nincs", "alacsony", "közepes", "magas", "nagyon magas"],  # Hungarian
}

# Names for the two allergy risk sensors per language. Used only when the
# user opts to name entities in the integration's configured language; the
# Home Assistant UI language is followed via translation keys otherwise.
RISK_SENSOR_NAMES = {
    "de": {
        "allergy_risk": "Allergierisiko",
        "allergy_risk_hourly": "Allergierisiko (stündlich)",
    },  # German
    "en": {
        "allergy_risk": "Allergy risk",
        "allergy_risk_hourly": "Allergy risk (hourly)",
    },  # English
    "fi": {
        "allergy_risk": "Allergiariski",
        "allergy_risk_hourly": "Allergiariski (tunneittain)",
    },  # Finnish
    "sv": {
        "allergy_risk": "Allergirisk",
        "allergy_risk_hourly": "Allergirisk (per timme)",
    },  # Swedish
    "fr": {
        "allergy_risk": "Risque d'allergie",
        "allergy_risk_hourly": "Risque d'allergie (horaire)",
    },  # French
    "it": {
        "allergy_risk": "Rischio allergia",
        "allergy_risk_hourly": "Rischio allergia (orario)",
    },  # Italian
    "lv": {
        "allergy_risk": "Alerģijas risks",
        "allergy_risk_hourly": "Alerģijas risks (pa stundām)",
    },  # Latvian
    "lt": {
        "allergy_risk": "Alergijos rizika",
        "allergy_risk_hourly": "Alergijos rizika (kas valandą)",
    },  # Lithuanian
    "pl": {
        "allergy_risk": "Ryzyko alergii",
        "allergy_risk_hourly": "Ryzyko alergii (godzinowe)",
    },  # Polish
    "pt": {
        "allergy_risk": "Risco de alergia",
        "allergy_risk_hourly": "Risco de alergia (por hora)",
    },  # Portuguese
    "ru": {
        "allergy_risk": "Риск аллергии",
        "allergy_risk_hourly": "Риск аллергии (почасовой)",
    },  # Russian
    "sk": {
        "allergy_risk": "Riziko alergie",
        "allergy_risk_hourly": "Riziko alergie (hodinové)",
    },  # Slovak
    "es": {
        "allergy_risk": "Riesgo de alergia",
        "allergy_risk_hourly": "Riesgo de alergia (por hora)",
    },  # Spanish
    "tr": {
        "allergy_risk": "Alerji riski",
        "allergy_risk_hourly": "Alerji riski (saatlik)",
    },  # Turkish
    "uk": {
        "allergy_risk": "Ризик алергії",
        "allergy_risk_hourly": "Ризик алергії (погодинний)",
    },  # Ukrainian
    "hu": {
        "allergy_risk": "Allergiakockázat",
        "allergy_risk_hourly": "Allergiakockázat (óránkénti)",
    },  # Hungarian
}

# Display name overrides per language, keyed by the English allergen slug.
# The API returns the English name for a few allergens even when a localized
# name exists, so the display name is corrected here. The name used to match
# against the API response is unaffected.
ALLERGEN_DISPLAY_OVERRIDES = {
    "de": {"ragweed": "Ambrosia"},  # German
    "sk": {"ragweed": "Ambrózia"},  # Slovak
}
