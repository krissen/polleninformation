# Helper Scripts for `polleninformation` Integration Development

Denna mapp innehåller flera fristående Python-skript som är avsedda att:

1. Hjälpa oss kartlägga vilka `country_id` som fungerar för olika länder/platser i polleninformation.at API:t.  
2. Validera och sanera de uppgifter vi samlar (t.ex. se till att platsen faktiskt ligger i rätt land).  
3. Migrera och uppdatera den lokala JSON-databasen `country_ids.json`.  
4. Tillhandahålla små “test‐verktyg” som vi kan köra manuellt eller automatiskt för att felsöka och verifiera enskilda API-anrop mot polleninformation.at.

> **Varje script är fristående**, men vissa använder gemensam JSON-fil (`country_ids.json`) som “databas/skriftligt register”.  
> Se avsnittet “Arbetsflöde” nedan för att förstå i vilken ordning de normalt körs.

---

## Översikt av filer

```bash
scripts/
├── test_pollenapi.py
├── test_pollenapi_countryid.py
├── test_pollenapi_multi.py
├── validate_tertiary_hits.py
├── migrate_slugs.py
├── generate_available_countries.py
└── README.md ← (denna fil)
```

### 1. `test_pollenapi.py`

**Syfte:**  
Ett litet “single‐call” skript för att göra ett enstaka API-anrop mot polleninformation.at – med valfri latitud, longitud, språkkod och landskod. Används främst för manuella tester och felsökning.

**Varför:**  
När vi vill se exakt hur ett enskilt anrop returnerar data, t.ex. vilket `pollution_date` och vilka pollennivåer som rapporteras för en given plats.

**Hur man använder det:**  

```bash
python scripts/test_pollenapi.py \
  --lat 59.3293 --lon 18.0686 \
  --country SE --country-id 26 \
  --lang de
--lat <float>: Latitud för platsen (t.ex. 59.3293).

--lon <float>: Longitud för platsen (t.ex. 18.0686).

--country <str>: Landskod (två bokstäver, t.ex. SE för Sverige). Om ej anges → standard är AT.

--country-id <int>: Det numeriska country_id som API:t förväntar sig (t.ex. 26 för Sverige).

--lang <str>: Språkkod (de eller en) för pollentitlar. Om ej anges → standard är de.
```

Exempel‐one-liner:

```
python scripts/test_pollenapi.py --lat 41.9029 --lon 12.4534 --country VA --country-id 14 --lang de
```

Testar Vatikanstaten (lat=41.9029, lon=12.4534) med country_id = 14.

### 2. test_pollenapi_countryid.py

**Syfte:**
Ett skript som itererar över alla potentiella country_id (i ett givet intervall), för en specifik plats (lat/lon + tvåbokstavskod). Används för att automatiskt upptäcka vilka country_id som faktiskt returnerar giltig pollen‐data för en plats.

Tidigare versioner utgick enbart från en “primär pool” (t.ex. 1…99).

När ett giltigt anrop hittas: sparas (plats → country_id) direkt i country_ids.json och skriptet avbryter loop för det landet.

**Varför:**
För att fylla på eller förnya vår country_ids.json med det country_id som rent tekniskt ger fokus‐API-data för en given lat/lon. Istället för att manuellt testa varje country_id, löper detta skript igenom flera möjligheter och sparar matchningen i JSON‐filen.

Grundläggande arbetsflöde:

Laddar in befintlig country_ids.json (om filen inte finns, skapas en tom struktur).

Kollar om landet (t.ex. "SE") redan har en sparad match i höger nod; om ja → hoppar över.

Annars loopar genom:

Primär pool: alla ID som ännu inte är “matchade” eller tidigare testade.

(– ”Sekundär pool” kan inaktiveras om ni vill förenkla – dvs. testa inte tidigare ogiltiga sådana.)

(– ”Tertiär pool” innehåller redan matchade ID för andra länder, i sista hand – om det skulle ge en oväntad cross‐match.)

När ett giltigt anrop (finns "contamination" i svaret) första gången hittas: markera country_id som “matchad” och spara in i JSON. Avbryt vidare test för detta land.

Körningsexempel:

```bash
python scripts/test_pollenapi_countryid.py \
  --lat 59.3293 --lon 18.0686 --country SE
```

Skriptet letar upp giltigt country_id för Sverige (om det inte redan finns inlagt).

JSON‐filen country_ids.json uppdateras med t.ex. "SE": { "country_ids": [26], "lat": 59.3293, … }.

Obs: Parametrarna --lang och --country-id brukar vara överflödiga här eftersom skriptet loopar egna ID‐värden internt. Du anger bara --lat, --lon och --country.

### 3. test_pollenapi_multi.py

**Syfte:**
Ett mer avancerat varianterat versionsskript av test_pollenapi_countryid.py. Den stöttar:

Primär pool: (ID som hittills aldrig har testats globalt/lokalt).

Tertiär pool: (ID som redan matchats mot andra länder, men aldrig testats mot aktuell plats).

Möjlighet att skriva “tillfälligt” tillbaka i 'tested' och 'invalid' utan att bryta om man avbryter med Ctrl-C.

“Graceful exit” vid Ctrl-C (skrivs ut vad som hittills är sparat).

Lagrar tre nyckelnoder i JSON:

"countries": kartläggning av landskod → (lista country_ids, lat, lon, place_slug/formatted osv).

"tested": per‐land lista över alla country_id‐värden som just detta skript provat.

"invalid": lista över country_id som verkligen gav ogiltigt/null‐svar (får aldrig matchas senare, men kan köras på nytt i undantagsfall).

När du använder detta:

Kör om du vill testa hela Europa (du ger in en lista av flertal EU-länder i koden).

För varje land i din EUROPEAN_LOCATIONS lista:

Om landet redan finns i db["countries"] → hoppa.

Annars kör primärpool (1…99 minus globalt matchade & egna testade & invalid).

Om inget hittas, hoppa tertiärpool (historiskt “matchade” ID).

Om inget hittas i någon pool → skriv ut “❌ Ingen giltig data…”.

Köra hela Europa (exempel):

```bash
python scripts/test_pollenapi_multi.py
```

– Skriptet använder den inbyggda EUROPEAN_LOCATIONS arrayen i koden för att stegvis fylla på country_ids.json för varje land.
– Efteråt: du har för varje landskod (t.ex. "FR", "DE", "IT") en verifierad matchning till ett eller flera country_id i JSON.

### 4. migrate_slugs.py

**Syfte:**
Efterhand kan vår algoritm för att “slugifiera” ett place_format (t.ex. ”75004 Paris”) förändras eller förbättras. Detta skript körs för att migrera alla gamla “place_slug” i country_ids.json till en enhetlig, ny form.

Vad den gör:

Laddar country_ids.json.

För varje land i "countries", hämtar info["place_format"] (t.ex. ”8001 Zürich”).

Genererar en ny slug med den uppdaterade slugify(...)-funktionen.

Om den nya slugen skiljer sig från befintlig place_slug i JSON → skriva över + uppdatera "last_updated".

I slutändan sparas en temporär .tmp-fil och byts ut mot originalet atomärt, så att du inte riskerar halvskriven fil.

Hur använda:

```bash
python scripts/migrate_slugs.py
```

Använd när du har ändrat extract_place_slug() eller slugify() i kodbasen och vill ensa alla befintliga poster.

### 5. validate_tertiary_hits.py

**Syfte:**
När vi har kört “tertiärpoolen” i test_pollenapi_multi.py, kan vissa “matchningar” vara falska positiva (t.ex. vi satte in ett country_id som egentligen bara gav data för en grannkommuns lat/lon). Detta skript kollar varje befintlig post i "countries" i JSON och “validerar” att platsen verkligen ligger i det land vi tror.

Granulärt flöde:

Laddar in country_ids.json.

För varje { country: info } i countries:

Hämta befintligt lat/lon från JSON (detta är koordinaten vi använde för att testa).

Hämta det sparade place_format (t.ex. “LV-4242 Ipiķi”).

Försök att geokoda med “hint” = “<place_format>, <country>” via geopy.

Om lyckad: få (lat2, lon2) samt bekräftat land.

Beräkna avstånd i km mellan (lat, lon) (ursprunglig sökpunkt) och (lat2, lon2).

Hämta landkod via en enkel “reverse‐lookup” på lat2/lon2.

Om landkod == förväntat → markera som valid. Annars → markera som invalid med skäl (t.ex. “felaktig landmatchning”).

Om “hint” ger ingen träff → försök utan hint (“<place_format>”).

Om fortfarande ingen träff → sätt landkod = None → markera för manuell kontroll i JSON.

I slutändan skapas (eller skrivs över) en ny version av country_ids.json där varje land‐node får en extra under‐nod "validation" med fältet:

```json
"validation": {
  "validated_at": "2025-06-01T12:34:56.789012+00:00",
  "valid": false,
  "reason": "felaktig landmatchning (förväntat=VA, geokodat=IT)",
  "found_country": "IT",
  "distance_km": 2.66
}
```

eller

```json
"validation": {
  "validated_at": "2025-06-01T12:34:56.789012+00:00",
  "valid": true,
  "country_matched": "SE",
  "distance_km": 0.25
}
```

Hur använda:

```bash
python scripts/validate_tertiary_hits.py
```

Detta är “dry‐run” och skriver direkt till samma JSON, men kan utökas att bara skriva till en temporär utdata (just nu uppdaterar det befintliga).

Kör om du vill säkerställa att alla sparade lat/lon & country_id faktiskt tillhör “rätt land”—eller för att flagga trippel‐träffar där vi lurats av att en granne gav data.

### 6. generate_available_countries.py

**Syfte:**
När vår country_ids.json är färdigvaliderad, vill vi generera ett “kompilerat” JSON‐utdrag som integrationen senare kan läsa in för att veta:

Vilka länder faktiskt stöds (landskod + fullständigt namn).

Vilka country_id som hör till varje land.

(Eventuellt) skapa en lista av språk‐alternativ eller kategorier.

Vad den gör (förslag):

Läser in “final” country_ids.json.

Använder interna Python‐moduler (t.ex. pycountry eller ett eget uppslagsverk) för att programmässigt hämta landet namn (”Sweden”, “Italy” osv) baserat på landskoden (“SE”, “IT”).

Skapar en ny JSON‐fil, t.ex. available_countries.json med struktur:

```json
{
  "SE": {
    "name": "Sweden",
    "country_id": [26],
    "place_slug": "stockholm"
  },
  "IT": {
    "name": "Italy",
    "country_id": [14],
    "place_slug": "roma"
  },
  … 
}
```

Sparar filen under custom_components/polleninformation/ (eller annat lämpligt ställe) så att integrationens Python-kod enklare kan ladda den utan att behöva kontakta API:t i realtid.

Hur använda (när allt annat är färdigt):

```bash
python scripts/generate_available_countries.py \
  > ../custom_components/polleninformation/available_countries.json
```

– Alternativt fannScriptet direkt spara → custom_components/polleninformation/available_countries.json.

Förutsättning:

Ett fullt uppdaterat och validerat country_ids.json.

En uppsättning av Python-beroenden, t.ex. pip install pycountry (för landnamnsuppslag).

## Arbetsflöde (exempel)

Fyll på “country_ids.json” med giltiga country_id

Kör python scripts/test_pollenapi_multi.py.

Detta går igenom samtliga länder i EUROPEAN_LOCATIONS (och efterfriskar primär/tertiärpool).

När ett giltigt svar hittas sparas: landskod → (country_id, lat, lon, place_slug, place_format).

Den sparade JSON‐filen innehåller nu en grunduppsättning stödda länder.

Validera alla “tertiära” träffar

Kör python scripts/validate_tertiary_hits.py.

Detta uppdaterar varje land‐post med en "validation"‐nod, som indikerar om platsen faktiskt ligger inom landets gränser.

Inspektera alla poster där "valid": false och korrigera manuellt (om nödvändigt) i country_ids.json.

(Om vi ändrat slug-logiken) Migrera befintliga “place_slug”

När vi förbättrat eller ändrat hur vi skapar place_slug, kör:

```bash
python scripts/migrate_slugs.py
```

Detta går igenom alla poster och uppdaterar “place_slug” i JSON så att de följer den nya metoden.

Generera ett “tillgängliga länder”-utdrag som integrationen kan läsa

När country_ids.json är korrekt och validerad, kör:

```bash
python scripts/generate_available_countries.py \
  > ../custom_components/polleninformation/available_countries.json
```

Detta skapar en kompakt JSON som innehåller varje lands fullständiga namn + den matchade country_id.

Den filen placeras direkt i integrationens katalog och används senare av PollenApi eller config_flow för att fylla i dropdown‐menyer mm.

## Kontinuerliga tester med enstaka API-anrop

Om du snabbt vill testa en specifik lat/lon + landskod, kör

```bash
python scripts/test_pollenapi.py \
  --lat 59.3293 --lon 18.0686 --country SE --country-id 26 --lang de
```

Använd detta för felsökning av enskilda koordinater eller för att bekräfta att integrationen just nu “fångar upp” ett särskilt allergen.

## Förutsättningar & Installation

Skapa en virtuell miljö (rekommenderat) och installera nödvändiga paket:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install aiohttp async-timeout geopy pycountry
```

aiohttp och async-timeout behövs för API-anropen.

geopy behövs för validering (reverse/hint geocoding).

pycountry (el. egen motsvarighet) behövs för att slå upp landnamn i generate_available_countries.py.

Se till att du har en tom (eller befintlig) country_ids.json i scripts/:

```json
{
  "countries": {},
  "tested": {},
  "invalid": []
}
```

Kontrollera att din scripts/-mapp är inspirerad av katalogstrukturen ovan, med korrekt filnamn.
Kör exempelvis:

```bash
ls scripts/
# → test_pollenapi.py  test_pollenapi_multi.py  validate_tertiary_hits.py  migrate_slugs.py  generate_available_countries.py
```

Kör de olika skripten i ordning enligt avsnittet “Arbetsflöde”. Varje steg uppdaterar country_ids.json så att nästa steg vet vad som är redan testat, ogiltigt eller matchat.

## Tips och Vanliga Fallgropar

### Avbrytning med Ctrl-C

Skript som test_pollenapi_multi.py och validate_tertiary_hits.py lyssnar på Ctrl-C och försöker göra en “graceful exit”. Datum/tider som redan sparats i JSON bör dock vara intakta, så du kan återuppta nästa gång utan förlust.

### Rate-begränsning

REQUEST_DELAY i test_pollenapi_multi.py är satt till 3 sekunder mellan förfrågningar. Behåll minst 1–3 sekunders paus per anrop för att undvika att överbelasta offentliga nominatim/OpenStreetMap-tjänster.

### Manuell korrigering

Om validate_tertiary_hits.py rapporterar att “landkod=nan” eller “landkod mismatch” för en post, bör du manuellt kontrollera och korrigera i country_ids.json.

### Slugs och Unicode

När du ändrar slugify(...) eller extract_place_slug(...), kör genast migrate_slugs.py så att samtliga tidigare sparade place_slug får det nya formatet. Annars riskerar dina tester att bli inkonsistenta.

### Dubbla Country_ID för ett land

Vissa länder har flera giltiga country_id (t.ex. Spanien kunde hittas med 31, 93 eller 98). Skriptet sparar bara det första det hittar. Vill du lista alla giltiga ID för ett land får du anpassa test_pollenapi_multi.py att inte avbryta direkt vid första match.

## Sammanfattning

`test_pollenapi.py`: Ett snabbt “single‐call” testverktyg.

`test_pollenapi_countryid.py` / test_pollenapi_multi.py: Loopa igenom country_id‐värden för att hitta och spara vilken ID som verkligen fungerar för varje land.

`validate_tertiary_hits.py:` Kör geokodning/omvänd geokodning för att kontrollera att varje plats/lat-lon faktiskt ligger i det land vi tror.

`migrate_slugs.py:` Uppdatera alla slugs i country_ids.json när vi förbättrar hur en slug skapas.

`generate_available_countries.py:` Konsumerar “färdig” och validerad country_ids.json och skapar ett JSON-utdrag med “landskod → landnamn + country_id”, avsett för integrationens UI/konfiguration.

Med denna uppdelning blir det lätt att både fylla på, validera och hålla JSON‐databasen uppdaterad. När den väl är färdig kan integrationens kod importera den kompilerade “available_countries.json” direkt, utan att behöva köra API-upptäckter i realtid.
