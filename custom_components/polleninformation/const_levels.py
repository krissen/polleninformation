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
