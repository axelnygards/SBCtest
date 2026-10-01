# FUT SBC Solver – Chrome-tillägg

Importerar din klubb och priser du själv ser i EA FC Web App till FUT SBC Solver.

## Vad tillägget gör och inte gör

| Gör | Gör aldrig |
|---|---|
| Kopierar svarsdata som Web App redan tar emot för klubb, transfermarknadssökningar, prisgränser och dina egna affärer (köp, bevakningslista, transferlista) | Läser lösenord, cookies, sessionsnyckel (`X-UT-SID`) eller andra request-headers |
| Vid **Importera klubb**: ber Web App:ens egen klubbsökning ladda nästa sida, en sida var 1,5 s, högst 70 sidor | Bygger egna anrop till EA:s servrar |
| Skickar klubben och (om du tillåter) de priser du sett till den server du angett | Köper, säljer, listar, budar eller söker på marknaden åt dig |
| | Döljer eller slumpar sitt beteende för att se mänskligt ut |

Allt detta testas i `test/e2e.mjs`: där får alla förfrågningar mot EA:s (simulerade) servrar
bara komma från Web App:ens egen kod.

**EA:s villkor:** EA har inte godkänt tillägget. EA:s officiella FC Community API är bara
öppet för FUT.GG, FUTBIN och FUTWIZ. Användningen sker på egen risk. Popup-fönstret visar
detta innan tillägget går att använda.

## Priser som delas (om du tillåter det)

| Källa | Vad som skickas |
|---|---|
| Dina sökningar på transfermarknaden | Lägsta köp-direkt-pris per kort bland träffarna |
| Ett kort du köper eller vinner | Priset du betalade (`sold`, en riktig affär) |
| Ett kort du säljer | Priset det såldes för (`sold`) |
| Bevakningslistan | Andra säljares köp-direkt-pris |
| Prisgränser när du listar | EA:s min- och maxpris för kortet |

Dina egna utropspriser på transferlistan skickas inte: de är en önskan, inte ett marknadspris.
Tillägget skickar aldrig vem du är, bara priset, kortet och plattformen.

## Behörigheter

- `storage`: kopplingskod och inställningar
- `activeTab`: kontrollera att aktiv flik är Web App när du trycker Importera
- Content scripts bara på `https://www.ea.com/*ea-sports-fc/ultimate-team/web-app/*`
- Nätverk bara mot servern du anger (`localhost:8000` som standard, annars efter fråga)

## Status

- Parsning: enhetstester (`npm test`)
- Hela flödet: end-to-end mot en simulerad Web App och riktig backend (`node test/e2e.mjs <db>`)
- **Inte verifierat mot EA:s riktiga Web App ännu.** Den automatiska importen bygger på Web
  App:ens globala `services.Club.search` och `UTSearchCriteriaDTO`, som kan heta annorlunda i
  FC 27. Om de saknas visar popupen det och faller tillbaka på passiv läsning: bläddra igenom
  klubben själv, så läser tillägget med.

## Installera (utvecklarläge)

1. `chrome://extensions` → slå på Utvecklarläge → **Läs in okomprimerat** → välj mappen `extension/`.
2. Öppna appen, skapa en kopplingskod och klistra in den i tilläggets popup.
3. Öppna EA FC Web App, logga in och tryck **Importera klubb**.
