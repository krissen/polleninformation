import re


def slugify(text: str) -> str:
    try:
        from unidecode import unidecode

        text = unidecode(text)
    except ImportError:
        # Fallback: bara ta bort diakritik (funkar ej för kyrilliska)
        text = (
            unicodedata.normalize("NFKD", text)
            .encode("ascii", "ignore")
            .decode("ascii")
        )
    text = text.split("(", 1)[0] if "(" in text else text
    text = text.strip().lower()
    text = text.replace("ö", "o").replace("ä", "a").replace("å", "a").replace("ß", "ss")
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"[^a-z0-9_]", "", text)
    return text


def extract_place_slug(full_location: str) -> str:
    full_location = full_location.strip()
    parts = full_location.split(maxsplit=1)
    if parts and re.match(r"^[A-Za-z0-9\-]+$", parts[0]) and len(parts) == 2:
        place_name = parts[1]
    else:
        place_name = full_location
    return slugify(place_name)


def split_location(locationtitle):
    locationtitle = locationtitle.strip()
    parts = locationtitle.split(maxsplit=1)
    if parts and re.match(r"^[A-Za-z0-9\-]+$", parts[0]) and len(parts) == 2:
        return parts[0], parts[1]
    return "", locationtitle
