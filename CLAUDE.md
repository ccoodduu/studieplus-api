# studieplus-api - Projektviden

## Projekt

Python-klient til Studie+ (pakken `studieplus_api`). Bruger GWT-RPC API direkte
(ingen browser) via `requests`-biblioteket.

Bruges af [studieplus-mcp](https://github.com/ccoodduu/studieplus-mcp) og
[studieplus-calendar](https://github.com/ccoodduu/studieplus-calendar), som begge
installerer nyeste `main` herfra. En ændring her rammer altså begge ved næste
geninstallation. **Kalenderen kører på en Raspberry Pi med Python 3.9**, så koden skal
være 3.9-kompatibel (ingen `X | Y` type-unions, ingen `match`).

Biblioteket læser ikke selv `.env`: credentials kommer fra argumenter eller
`STUDIEPLUS_*` environment variables, som programmet der bruger det sætter.

### Krav til GWT-parsing
- **INGEN magic numbers** eller hacky løsninger
- **Parse data på SAMME måde som JavaScript-koden gør** (stack-baseret)
- Hvis der er udfordringer: **meld tilbage i stedet for at ændre plan**
- **ALTID** følg JS-kodens læserækkefølge

---

## GWT-RPC Format

### Response struktur
```
//OK[data..., ["string_table"], flags, version]
```

- `//OK` eller `//EX` prefix (success/exception)
- `data` - flat array, læses bagfra (stack)
- `string_table` - 1-baseret indeksering (0 = null)

### Læsefunktioner
- `a.b[--a.a]` — pop int fra stack
- `pqd(a, val)` — string lookup: `val > 0 ? strings[val-1] : null` (SINGLE pop, babel-inlined version ser ud som 2 pops men er 1)
- `!!a.b[--a.a]` — boolean
- `iqd(a)` — objekt: pop, negativ=back-reference, positiv=klasse fra string table, 0=null

---

## Vigtige Deserializers

### Note (Lzg — source_babel_inlined.js:26658)
Top-level response fra `hentNoteForSkema(lessonId)`.
```javascript
function Lzg(a, b) {
  b.a = zUb(iqd(a), 24);    // Integer (SkemaObjekt ID)
  b.b = zUb(iqd(a), 169);   // Medarbejder (lærer)
  b.c = zUb(iqd(a), 211);   // SkemaNote2
}
```

### SkemaNote2 (hAg — source_babel_inlined.js:53626)
16 felter. **VIGTIGT:** `b.c` er IKKE fil-container. `b.n` er fil-container.
```
b.a  = int              — note ID
b.b  = string           — klasse-navn (f.eks. "htxqr24")
b.c  = int              — schedule container_id (IKKE til filer!)
b.d  = boolean          — has_files
b.e  = string           — lektier tekst
b.f  = string           — lektier HTML
b.g  = string           — note tekst
b.i  = string           — note HTML
b.j  = object (Integer) — schedule container (samme som b.c)
b.k  = string
b.n  = object (Integer) — FILE container_id (BRUG DENNE til filer!)
b.o  = object (UDate)
b.p  = object (Integer)
b.q  = int
b.r  = int
b.s  = string
```

### SkemaBegivenhed (Dqg — source_babel_inlined.js:62180)
Vigtige felter:
- `b.P` = skoleFag (subject/fag)
- `b.Q` = slut (UDate)
- `b.R` = start (UDate)
- `b.A` = lokaleList (ArrayList af LokalerISkema)
- `b.C` = medarbejderList (ArrayList af MedarbejderISkema)

### ArrayList, UDate, LokalerISkema, MedarbejderISkema
Se `gwt_deserializer.py` for implementering — følger JS præcist.

### Klasse-opslag er EKSAKT
`_read_object` slår deserializer op på præcist klassenavn (før `/hash`). Tidligere prefix-match fik
`SkemaBegivenhed$ElevISkema` til at blive læst som en hel `SkemaBegivenhed` → stack drift i uger med den type.
`parse_schedule_response(..., strict=True)` fejler højlydt på uregistrerede klasser i stedet for at returnere [].

---

## Fil-download Flow (3 trin)

Bekræftet via Playwright network capture. Websiden bruger dette flow:

1. **`skemanoteservice.hentNoteForSkema(lessonId)`** → Note objekt med SkemaNote2
2. **`ressourceservice.findRessourcerPerContainer(file_container_id, SKEMANOTE=12)`** → filliste
3. **`ressourceservice.hentRessourceUrl(fileId, "")`** → signeret S3 URL

`file_container_id` kommer fra SkemaNote2 felt `b.n` (IKKE `b.c`).
`hentRessourceUrl` tager fil-ID og en TOM string som 2. parameter.

### Signerede URLs
Format: `https://cellar-c2.services.clever-cloud.com/prod-{instnr}/{uuid}?X-Amz-...`
Gyldige i ~5 minutter.

---

## Tests

Live contract-tests der logger ind og kalder det rigtige Studie+ API. De asserter
på *form* (typer, ranges, fornuftige værdier) — ikke specifikke værdier — for at
fange når Studie+ ændrer deres GWT-struktur.

### Kør tests
```bash
python -m pytest
```
Konfiguration ligger i `pytest.ini` (`testpaths = tests`, `asyncio_mode = auto`).

### Krav
- Credentials i `.env` i projektroden: `STUDIEPLUS_USERNAME`, `STUDIEPLUS_PASSWORD`,
  `STUDIEPLUS_SCHOOL`. Mangler de, **skippes** testene (fejler ikke).
- `pip install -r requirements-dev.txt` (installerer pakken editable + `pytest`, `pytest-asyncio`, `python-dotenv`).

### Filer
- `tests/conftest.py` — `scraper`-fixture (login) + shape-helpers
  (`assert_lesson_shape`, `assert_assignment_shape`, `assert_file_shape`,
  `looks_like_gwt_leak`).
- `tests/test_live.py` — live-testene, inkl. et 6-ugers vindue parset strict.
- `tests/test_gwt_deserializer.py` — offline tests med et syntetisk GWT-svar (rigtige svar
  indeholder andre elevers navne og må ikke committes).

**Bemærk:** Æ/ø/å vises som `�` i PowerShell-output pga. terminal-encoding —
selve dataen er korrekt.

---

## Hent GWT-kildekoden live

`gwt_analysis/`-filerne findes ikke i repo'et. For at reverse engineere en ny type:
1. Efter login + et servicekald har scraperen `skema_permutation`.
2. Hent `{base_url}/skema/skema/{perm}.cache.js` med `scraper.session.get(...)` (~2 MB).
3. Find klasse-variablen: `(\w+)='dk\.uddata\.model\.skema\.<Klasse>/'`.
4. Find registry-entry `a[VAR]=[instantiate, deserialize, serialize]` — den **midterste** er deserializeren.
5. Port 1:1 i JS-rækkefølge (funktionsnavnene skifter mellem permutationer; kig efter mønstret
   `a.b[--a.a]` = int, streng-læser med `a.b[--a.a]` som argument, objekt-læser `xxx(a)`).

Diagnose af stack drift: `parse_schedule_response(raw, strict=True)` rejser med klassenavnet
(eller antal ulæste værdier). Hent flere uger frem og tilbage — nye typer optræder kun i
nogle uger (fx `Fraver`, `SkemaBegivenhed$ElevISkema`).

---

## Vigtige Filer

- `src/studieplus_api/gwt_deserializer.py` — Stack-baseret GWT parser
- `src/studieplus_api/requests_scraper.py` — HTTP-baseret scraper (GWT-RPC kald)
- `GWT_REVERSE_ENGINEERING.md` — Guide til at reverse engineere nye GWT typer
