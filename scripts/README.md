# Helper Scripts för polleninformation-integration

**Legacy note:** Denna katalog innehåller skript som inte längre aktivt underhålls. De finns kvar som referens och kan användas vid behov men omfattas inte av reguljär support.

Dessa skript är fristående och används för att:

- Upptäcka vilka country_id och orter som fungerar mot polleninformation.at-API:t
- Validera, sanera och migrera vår egna JSON-databas (`country_ids.json`)
- Testa och felsöka API-anrop snabbt under utvecklingen

Alla script är fristående men använder vanligtvis en gemensam JSON-fil (`country_ids.json`) som “databas” för att spara och återanvända upptäckta ID och metadata.

## Innehåll

```text
scripts/
├── test_pollenapi.py
├── test_pollenapi_countryid.py
├── test_pollenapi_multi.py
├── validate_tertiary_hits.py
├── migrate_slugs.py
├── generate_available_countries.py
└── README.md   ← (denna fil)
```

## Scriptöversikt

### 1. test_pollenapi.py

**Syfte:**  
Testa ett enstaka API-anrop mot polleninformation.at för valfri plats och landskod.

**När?**

Vid manuell felsökning eller för att se exakta värden för en lat/lon/kombination.

**Kör så här:**

```bash
python scripts/test_pollenapi.py --lat 59.3293 --lon 18.0686 --country SE --country-id 26 --lang de
```

Alla parametrar (--lat, --lon, --country, --country-id, --lang) är valfria men kan anges för att testa olika kombinationer.

## 2. test_pollenapi_countryid.py

**Syfte:**

Testar alla möjliga country_id-värden för en plats/land och upptäcker vilket id som faktiskt returnerar pollen-data.

**Kör så här:**

```bash
python scripts/test_pollenapi_countryid.py --lat 59.3293 --lon 18.0686 --country SE
```

Fyller automatiskt på country_ids.json med nya fynd.

### 3. test_pollenapi_multi.py

**Syfte:**

Loopar genom en hel lista av länder (och lat/lon) för att försöka hitta alla fungerande country_id automatiskt. Bygger upp hela country_ids.json i batch.

**Kör så här:**

```bash
python scripts/test_pollenapi_multi.py
```

Uppdaterar JSON med varje lyckad match.

### 4. migrate_slugs.py

**Syfte:**

Efterhand vi ändrar reglerna för “slug” (tex ortsnamn) – migrera så alla gamla poster i JSON får ny, enhetlig slug.

**Kör så här:**

```bash
python scripts/migrate_slugs.py
```

### 5. validate_tertiary_hits.py

**Syfte:**

Kör validering av samtliga upptäckta poster i country_ids.json. Kollar så att ort, land och position verkligen stämmer, och markerar annars för manuell kontroll.

**Kör så här:**

```bash
python scripts/validate_tertiary_hits.py
```

Uppdaterar “validation”-fälten i JSON med resultatet.

### 6. generate_available_countries.py

**Syfte:**

Tar en färdig och validerad country_ids.json och genererar ett kompakt utdrag (available_countries.json) med endast de länder och id som integrationen faktiskt stödjer – och som läses av integrationen i Home Assistant.

**Kör så här:**

```bash
python scripts/generate_available_countries.py > ../custom_components/polleninformation/available_countries.json
```

Eller låt scriptet spara direkt på rätt plats.

## Arbetsflöde – Exempel

### Upptäck fungerande country_id

Kör test_pollenapi_multi.py för att fylla på JSON.

### Validera

Kör validate_tertiary_hits.py för att säkerställa att posterna är korrekta.

### Migrera vid behov

Om slug-logiken ändras, kör migrate_slugs.py.

### Generera slutanvändarfil

Kör generate_available_countries.py för att skapa JSON:en till integrationen.

## Tips

Bygg alltid på en färsk, validerad JSON.

Alla filoperationer är synkrona – vill du använda i HA/async, ladda in data via executor-jobb.

Rate-limita alltid API-anropen för att inte blockeras av polleninformation.at eller OSM.

Se till att pip-installera beroenden:

```bash
pip install aiohttp async-timeout geopy pycountry voluptuous
```
