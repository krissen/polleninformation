#!/usr/bin/env python3
import json
import os
from datetime import datetime, timezone

import pycountry

# Filnamn för den befintliga databasen
DB_FILE = "country_ids.json"
# Sökväg där den genererade filen ska sparas (relativt skriptets plats)
OUTPUT_FILE = os.path.join(
    os.path.dirname(__file__),
    "../custom_components/polleninformation/available_countries.json",
)


def get_country_name(alpha2_code: str) -> str | None:
    """
    Försöker slå upp landsnamn med hjälp av pycountry baserat på tvåbokstavskoden.
    Returnerar None om inget land hittas.
    """
    try:
        country = pycountry.countries.get(alpha_2=alpha2_code.upper())
        if country:
            return country.name
    except (KeyError, AttributeError):
        pass
    return None


def main():
    if not os.path.exists(DB_FILE):
        print(f"Fel: Kunde inte hitta {DB_FILE}.")
        return

    with open(DB_FILE, "r", encoding="utf-8") as f:
        db = json.load(f)

    available_countries = []

    for code, info in db.get("countries", {}).items():
        # Hämta det "riktiga" landsnamnet via pycountry
        name = get_country_name(code)
        if not name:
            # Om pycountry inte har just denna kod, varna och hoppa över
            print(
                f"🔶 Varning: Kunde inte slå upp landnamn för landskod '{code}'. Skippas."
            )
            continue

        # Lägg till i listan över tillgängliga länder
        available_countries.append(
            {"code": code, "name": name, "country_id": info.get("country_ids", [])}
        )

    # För att ge en indikation på när denna lista skapades:
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "countries": available_countries,
    }

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Skapade: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
