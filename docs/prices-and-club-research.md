# Livepriser och klubbimport: research (2026-09-30)

## Pris-API:er

| Leverantör | Pris | Anrop/dag | Uppdatering | FC 27 | Kommentar |
|---|---|---|---|---|---|
| [futdatabase.com](https://www.futdatabase.com/) | Gratis 14 dagar (5 000/dag), €49/mån, €469,99/säsong | 20 000 (betald) | 30 min–24 h (höga betyg oftare) | Ej bekräftat (sajten visar FC 26) | API-nyckel, JSON REST. Bäst att testa först. |
| [fut-db.com](https://fut-db.com/) | Priser kräver premium, €79/mån | 20 000 | 30 min–24 h | Ej bekräftat (sajten visar FC 26) | Ett pris per anrop, inga batch-anrop. Samma upplägg som ovan, möjligen samma aktör. |
| "Futbin API" på parse.bot | – | – | – | – | Inofficiell skrapning av Futbin. **Används inte** (bryter mot Futbins villkor). |
| FUTBIN / FUT.GG / FUTWIZ | – | – | Live | Ja | Inget publikt pris-API. |

**Budget för anrop:** med 20 000 anrop/dag och ett pris per anrop räcker det att prioritera
fodder-kort (guld ≥ 75, cirka 5 000 kort). Då uppdateras höga betyg (83+) varje timme och
resten några gånger per dag.

**Livelager:** tillägget sparar priser som användaren själv ser i Web App (sökresultat på
transfermarknaden och EA:s prisgränser vid listning). De ersätter API-priset för just de
korten. Tillägget gör aldrig egna sökningar.

## Klubbimport: EA:s officiella FC Community API

EA:s pitch notes ([FC Community API](https://www.ea.com/games/ea-sports-fc/fc-26/news/pitch-notes-fc26-community-api-update)):
- Officiellt API sedan 27 juli 2026. Användaren loggar in via EA:s eget flöde och ger en sajt
  rätt att hämta klubbdata. Sajten får aldrig lösenordet.
- **Bara FUT.GG, FUTBIN och FUTWIZ är godkända.** EA tar inte emot nya ansökningar just nu.
- EA varnar uttryckligen: "If you see an EA login flow on any other website claiming to offer
  FC API access, it should not be trusted."
- Data får sparas i högst 28 dagar.

**Konsekvens för oss:**
- Vi får inte använda Community API och ska aldrig visa något som liknar en EA-inloggning.
- Tillägget som läser Web App-data passivt är fortfarande möjligt, men det står nu tydligare
  utanför EA:s godkända väg.
- För förtroendets skull ska installationsflödet säga detta rakt ut. Om EA öppnar programmet
  för ansökningar söker vi.
