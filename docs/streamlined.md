# FC 27: poäng-SBC:er (Streamlined SBCs)

FC 27 bytte ut de flesta spelar- och uppgraderings-SBC:erna mot ett poängsystem. Varje kort
har ett fast **Item Score** som beror på betyget, och du lämnar in kort tills du når målet.
Chemistry, positioner, ligor, nationer och lagbetyg spelar ingen roll. Dubbletter är
tillåtna och delinlämningar sparas. Vissa SBC:er har ett lägsta betyg per kort.

Pussel-SBC:er (Marquee Matchups, Daily Puzzles, liga/nation-hybrider) har kvar det gamla
formatet och löses av CP-SAT-lösaren.

Källor: [Destructoid, EA:s pitch notes](https://www.destructoid.com/fc-27-ultimate-team-deep-dive-pitch-notes/),
[games.gg](https://games.gg/ea-sports-fc-27/guides/fc-27-streamlined-sbcs-explained/).

## Poängtabell (efter lansering)

| Betyg | Poäng | Betyg | Poäng | Betyg | Poäng |
|---|---|---|---|---|---|
| Brons (45–64) | 20 | 81 | 280 | 90 | 14 000 |
| Silver (65–74) | 35 | 82 | 340 | 91 | 19 000 |
| 75 | 90 | 83 | 410 | 92 | 20 000 |
| 76 | 100 | 84 | 830 | 93 | 25 000 |
| 77 | 120 | 85 | 2 100 | 94 | 30 000 |
| 78 | 140 | 86 | 4 100 | 95 | 40 000 |
| 79 | 160 | 87 | 5 500 | 96 | 55 000 |
| 80 | 180 | 88 | 8 300 | 97 | 85 000 |
| | | 89 | 11 000 | 98–99 | 90 000 / 100 000 |

Källor: [allthings.how (2026-09-22)](https://allthings.how/fc-27-streamlined-sbcs-how-the-item-score-system-works/)
och [starcitizenguides.net (2026-09-28)](https://www.starcitizenguides.net/2026/09/28/fc-27-streamlined-sbcs-item-score-explained/)
ger samma värden. En äldre tabell från före lanseringen (83 = 50, 85 = 65, timesaver.gg)
används inte.

**Specialkort och holografiska kort** ger enligt EA fler poäng än baskort med samma betyg,
men bonusen är inte publicerad. Lösaren räknar dem som baskort, så den överskattar aldrig.
Tabellen ligger i `backend/app/solver/streamlined.py` och är lätt att justera.

## Lösaren

Minsta kostnad för att nå målet är ett **täckande knapsackproblem**, som löses exakt med
dynamisk programmering på millisekunder:

- **Egna kort:** varje kort högst en gång. Kostnaden är vad du förlorar: säljvärdet × 0,95
  (EA:s skatt). Ej säljbara kort kostar 1, så de används först men inte i onödan.
- **Marknaden:** valfritt antal av det billigaste kortet per betyg. I praktiken stiger priset
  när man köper många, så appen visar "vilket kort som helst med samma betyg".
- Tillstånden är poäng kapade vid målet, i enheter av största gemensamma delaren av
  poängvärdena (5).

Testat mot uttömmande genomsökning (`tests/test_streamlined.py`). 20 000 poäng med 1 500 egna
kort tar ~0,1 s.

## Exempel (platshållarpriser)

| SBC | Mål | Billigast |
|---|---|---|
| 83+ Upgrade | 2 500 | 1 × 77 + 1 × 81 + 1 × 85 |
| Ones to Watch: Bouaddi | 20 000 | 5 × 86 |
