import json
import os
import time

import requests

# ================================
# KONFIGURATION
# ================================

LAT = 48.2081743
LON = 16.3738189
COUNTRY = "AT"
C_ID = 1  # country_id för Wien
DB_FILE = "custom_components/polleninformation/language_map.json"
DELAY_SEC = 3
L_RANGE = list(range(0, 101))  # Ändra om du vill testa fler L
HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148",
}


def load_db():
    if not os.path.exists(DB_FILE):
        return {}
    with open(DB_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_db(db):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)


def extract_name_and_latin(poll_title):
    if "(" in poll_title and ")" in poll_title:
        name = poll_title.split("(", 1)[0].strip()
        latin = poll_title.split("(", 1)[1].split(")", 1)[0].strip()
    else:
        name = poll_title.strip()
        latin = ""
    return {"name": name, "latin": latin}


def main():
    db = load_db()
    for L in L_RANGE:
        strL = str(L)
        if strL in db:
            print(f"L={L}: Already tested, skipping.")
            continue

        url = (
            f"https://www.polleninformation.at/index.php?"
            f"id=536&type=15976824&L={L}&C={C_ID}"
            f"&tx_scapp_appapi%5Baction%5D=getFullContaminationData"
            f"&locationType=gps&personal_contamination=false&sensitivity=0"
            f"&country={COUNTRY}&sessionid=&pasyfo=0"
            f"&value%5Blatitude%5D={LAT}&value%5Blongitude%5D={LON}"
        )
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            data = resp.json()
            result = data.get("result", {})
        except Exception as e:
            print(f"L={L}: [request error: {e}]")
            db[strL] = {"error": str(e)}
            save_db(db)
            time.sleep(DELAY_SEC)
            continue

        contamination_date_1 = result.get("contamination_date_1", "")
        poll_titles = [
            extract_name_and_latin(poll.get("poll_title", ""))
            for poll in result.get("contamination", [])
            if poll.get("poll_title")
        ]
        # Spara även alla fält i additionalForecastData (enbart keys, inte värden)
        additional_keys = []
        add_data = result.get("additionalForecastData", [])
        if add_data and isinstance(add_data, list):
            # Ta första elementet och samla alla keys (utom 'date', 'dayrisk_personalized')
            keys = [
                k
                for k in add_data[0].keys()
                if k not in ("date", "dayrisk_personalized")
            ]
            additional_keys = sorted(keys)
        # Spara posten eller error
        if not poll_titles and not additional_keys:
            db[strL] = {"error": "No data returned"}
            print(f"L={L}: Tomt resultat – sparar som error.")
            save_db(db)
            time.sleep(DELAY_SEC)
            continue

        entry = {
            "contamination_date_1": contamination_date_1,
            "poll_titles": poll_titles,
            "additional_forecast_keys": additional_keys,
            "language_id": "",  # Placeholder, kan mappas senare
        }
        # Uteslut tomma fält
        entry = {k: v for k, v in entry.items() if v}
        db[strL] = entry
        print(
            f"L={L}: {contamination_date_1!r}, poll_titles: {poll_titles!r}, additional_keys: {additional_keys!r}"
        )
        save_db(db)
        time.sleep(DELAY_SEC)

    print("Done. See", DB_FILE)


if __name__ == "__main__":
    main()
