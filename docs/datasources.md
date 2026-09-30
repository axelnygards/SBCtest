# Datakällor

Alla källor implementeras bakom `DataSource`-gränssnittet (`backend/app/datasources/base.py`).
Varje källa kan slås av/på via miljövariabler.

| Källa | Vad den ger | Status | Flagga |
|---|---|---|---|
| EA:s betygsdatabas | Basspelare FC 27: id, betyg, namn, nation, klubb, liga, positioner | **På** | `SOURCE_EA_RATINGS_ENABLED` |
| Chrome-tillägget | Din klubb, priser (prisgränser/marknad), SBC-krav, specialkort | **På** (tar emot push från tillägget) | alltid på |
| Futbin | Priser, SBC:er | **Av** – Cloudflare-spärr | `SOURCE_FUTBIN_ENABLED` |

## 1. EA:s betygsdatabas (basspelare, FC 27)

Två öppna läsvägar utan inloggning ger samma poster:

| Läge | URL | Storlek/sida |
|---|---|---|
| `api` | `https://drop-api.ea.com/rating/ea-sports-fc?limit=100&offset=N&locale=en` | ~40 kB |
| `site` | `https://www.ea.com/_next/data/<buildId>/games/ea-sports-fc/ratings.json?page=N` | ~1 MB |

`site` är JSON-datan bakom EA:s egen betygssida (www.ea.com/games/ea-sports-fc/ratings).
`buildId` läses från sidans `__NEXT_DATA__` och hämtas om vid 404 (ny deploy hos EA).

**Säsongsbyte (verifierat 2026-09-30):** betygssidan visar redan **FC 27** (19 789 spelare,
Mbappé/Haaland/Putellas 91), medan API:et fortfarande ger **FC 26** (17 873 spelare,
Salah 91 överst). Parametern `iteration` finns men är tom, och inga `ea-sports-fc-27`-slugs
finns (204). Läget `auto` jämför första sidan från båda och använder API:et först när det
ger samma data som sidan. Tills dess används `site`.

Anropen görs i tur och ordning, minst 1 s isär, med backoff vid 429/5xx. Inget skydd kringgås.

Postens fält (samma i båda lägena):

```jsonc
{
  "id": 231747,                 // = FUT resourceBaseId för baskortet
  "rank": 1, "overallRating": 91,
  "firstName": "Kylian", "lastName": "Mbappé", "commonName": null,
  "leagueName": "LALIGA EA SPORTS",
  "gender": {"id": 0, "label": "Men's Football"},
  "nationality": {"id": 18, "label": "France"},          // FUT nation-id
  "team": {"id": 243, "label": "Real Madrid"},           // FUT klubb-id
  "position": {"id": "25", "shortLabel": "ST"},
  "alternatePositions": [{"id": "27", "shortLabel": "LW"}],
  "stats": {...}, "playerAbilities": [...], "avatarUrl": "...", "shieldUrl": "..."
}
```

**Liga-id:** posten har bara liganamnet, men filtren (`ratingsFilters.teamGroups` på sidan,
eller `GET /rating/ea-sports-fc/filters`) listar varje liga med FUT-liga-id och dess klubbar,
t.ex. `{"id": "2149", "label": "ISL", "teams": [...]}`. Klubb → liga slås upp därifrån.
Okända klubbar får ett stabilt negativt pseudo-id från liganamnet.

**Begränsningar:** bara baskort (inga specialkort, ingen raritet, inga priser). Bildvägarna
heter `FC25/` även för FC 27-data och säger inget om säsongen.

Kör importen: `python -m app.datasources.ea_ratings --out players.jsonl` (~200 sidor, ~8 min).

## 2. EA FC Web App (via Chrome-tillägget)

Tillägget **läser bara** JSON som webbappen själv redan hämtar. Det gör inga egna anrop mot
EA, automatiserar inget och läser eller skickar aldrig inloggningsuppgifter eller tokens.
Det injicerar ett skript i sidans kontext som omsluter `fetch`/`XMLHttpRequest` och kopierar
**svarskroppen** för utvalda sökvägar. Request-headers (där `X-UT-SID` finns) läses aldrig.

Värd (varierar per säsong): `https://utas.mob.v*.prd.futc-ext.gcp.ea.com/ut/game/fc27/...`

| Sökväg (mönster) | Innehåll | Används till |
|---|---|---|
| `/club` (POST, sökning i klubben) | `itemData[]` med spelare | Import av klubben |
| `/purchased/items`, `/storagepile` | Obundna/förråd | Import |
| `/sbs/sets` | SBC-kategorier och set | SBC-lista |
| `/sbs/setId/{id}/challenges` | Utmaningar med `elgReq[]` | SBC-krav |
| `/marketdata/item/pricelimits` | Min/max-pris per `itemId` | Prisuppskattning |
| `/transfermarket` | Auktioner (`buyNowPrice`) | Prisobservationer |

Spelarobjekt (`itemData`), relevanta fält:
`id, assetId, resourceId, rating, rareflag, preferredPosition, possiblePositions, nation,
leagueId, teamid, untradeable, loans, itemType`.

SBC-krav (`elgReq`): `{type, eligibilityKey, eligibilitySlot, eligibilityValue, scope}`
där `scope` är `GREATER` / `LOWER` / `EXACT`. Nyckelnumren mappas i
`backend/app/sbc/eligibility.py`. **Mappningen är inte verifierad mot fångad data i FC 26.**
Råkraven sparas alltid, och okända nycklar flaggas i UI:t i stället för att tyst ignoreras.

## 3. Futbin (avstängd)

`https://www.futbin.com` svarar `403` med Cloudflare-utmaning mot vanliga HTTP-klienter.
Vi kringgår inte skyddet. Adaptern finns (`futbin.py`) med samma gränssnitt men är avstängd
som standard och gör ingenting förrän en tillåten åtkomstväg finns (t.ex. officiellt API).
