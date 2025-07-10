""" custom_components/polleninformation/utils.py """
import re
import unicodedata

def slugify(text: str) -> str:
    """Konverterar text till slug: gemener, ASCII, inga parenteser, endast a-z0-9_."""
    try:
        from unidecode import unidecode
        text = unidecode(text)
    except ImportError:
        text = (
            unicodedata.normalize("NFKD", text)
            .encode("ascii", "ignore")
            .decode("ascii")
        )

    # Ta bort parentesinnehåll
    text = text.split("(", 1)[0] if "(" in text else text
    text = text.strip().lower()

    # Ersätt diakrit-variationer och specialfall
    text = (
        text.replace("ö", "o")
        .replace("ä", "a")
        .replace("å", "a")
        .replace("ß", "ss")
        .replace("'", "")   # Tar bort apostrofer från translit
    )

    # Ersätt alla icke-alfanumeriska tecken med _
    text = re.sub(r"[^\w]+", "_", text)

    # Ta bort inledande och avslutande _
    text = text.strip("_")

    return text

def extract_place_slug(full_location: str) -> str:
    """Returnerar slugifierat platsnamn utan ev. postnummer/kod före första mellanslag."""
    full_location = full_location.strip()
    parts = full_location.split(maxsplit=1)
    if parts and re.match(r"^[A-Za-z0-9\-]+$", parts[0]) and len(parts) == 2:
        place_name = parts[1]
    else:
        place_name = full_location
    return slugify(place_name)

def split_location(locationtitle):
    """Dela locationtitle till (postnummer/kod, namn) – annars ('', locationtitle)."""
    locationtitle = locationtitle.strip()
    parts = locationtitle.split(maxsplit=1)
    if parts and re.match(r"^[A-Za-z0-9\-]+$", parts[0]) and len(parts) == 2:
        return parts[0], parts[1]
    return "", locationtitle

