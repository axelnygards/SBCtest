# Datakällor

Alla källor implementeras bakom `DataSource`-gränssnittet (`backend/app/datasources/base.py`).
Varje källa kan slås av/på via miljövariabler.

| Källa | Vad den ger | Status | Flagga |
|---|---|---|---|
| EA ratings-API | Basspelare: id, betyg, namn, nation, klubb, liga (namn), positioner | **På** (kräver att `drop-api.ea.com` är nåbar) | `SOURCE_EA_RATINGS_ENABLED` |
| Chrome-tillägget | Din klubb, priser (prisgränser/marknad), SBC-krav, specialkort | **På** (tar emot push från tillägget) | alltid på |
| Futbin | Priser, SBC:er | **Av** – Cloudflare-spärr | `SOURCE_FUTBIN_ENABLED` |

## 1. EA ratings-API (öppet)

```
GET https://drop-api.ea.com/rating/ea-sports-fc?limit=100&offset=0&locale=en
```

Besvarades med `200` och JSON vid test (tidigare session). Svaret är sidindelat:

```jsonc
{
  "totalItems": 17000,          // ungefärligt
  "items": [{
    "id": 231747,               // = FUT resourceBaseId för baskortet
    "rank": 1,
    "overallRating": 91,
    "firstName": "Kylian", "lastName": "Mbappé", "commonName": null,
    "leagueName": "LALIGA EA SPORTS",   // OBS: bara namn, inget liga-id
    "gender": {"id": 0, "label": "Male"},
    "nationality": {"id": 18, "label": "France", "imageUrl": "..."},
    "team": {"id": 243, "label": "Real Madrid", "imageUrl": "..."},
    "position": {"id": 25, "shortLabel": "ST", "label": "Striker"},
    "alternatePositions": [{"id": 27, "shortLabel": "LW"}],
    "avatarUrl": "...", "shieldUrl": "...",
    "stats": {...}, "playerAbilities": [...]
  }]
}
```

Fältnamnen ovan kommer från tidigare test och från hur appen läser dem. Adaptern
(`ea_ratings.py`) läser fälten defensivt och sparar hela råposten i `players.raw` så att
mappningen kan justeras utan att data hämtas igen.

**Begränsningar**
- Bara baskort (inga specialkort, ingen raritet, inga priser).
- Liga ges som namn. Liga-id hämtas från tilläggets data (klubbens `leagueId`), och tills dess
  används ett stabilt pseudo-id från ligans namn.
- **Molnmiljön blockerar just nu `drop-api.ea.com` (403 från egress-proxyn).** Värden
  måste läggas till i miljöns nätverksinställningar. Tills dess körs testerna mot fixture-data.

## 2. EA FC Web App (via Chrome-tillägget)

Tillägget **läser bara** JSON som webbappen själv redan hämtar. Det gör inga egna anrop mot
EA, automatiserar inget och läser eller skickar aldrig inloggningsuppgifter eller tokens.
Det injicerar ett skript i sidans kontext som omsluter `fetch`/`XMLHttpRequest` och kopierar
**svarskroppen** för utvalda sökvägar. Request-headers (där `X-UT-SID` finns) läses aldrig.

Värd (varierar per säsong): `https://utas.mob.v*.prd.futc-ext.gcp.ea.com/ut/game/fc2x/...`

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
