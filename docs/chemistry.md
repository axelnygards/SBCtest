# Chemistry-regler

Reglerna är versionerade i `backend/app/solver/rules.py` (`CHEM_RULES["fc26"]`,
`CHEM_RULES["fc27"]`). Standard är `fc27`, som är aktuell säsong (september 2026).

## Gemensamt (FC 24 → FC 27)

- En spelare har 0–3 i chemistry. Laget har högst 33 (11 × 3).
- En spelare får chemistry **och** räknas mot trösklarna bara om den står i en av sina
  giltiga positioner (primär plus alternativa). Står den fel får den 0 och bidrar inte.
- Poängen kommer från tre länkar: klubb, liga och nation. Summan kapas vid 3.

| Antal i position | Klubb | Liga | Nation |
|---|---|---|---|
| +1 | 2 | 3 | 2 |
| +2 | 4 | 5 | 5 |
| +3 | 7 | 8 | 8 |

- Damer och herrar länkar via klubb och nation. Liga länkar inte, eftersom ligorna är skilda.
- Managerbonusen (+1, kapad) finns i vanliga lag men **inte i SBC:er**. Lösaren ignorerar den.
- Lånespelare räknas som vanliga spelare.

## Icons och Heroes (i position)

| | FC 26 | FC 27 |
|---|---|---|
| Icon: egen chemistry | alltid 3 | alltid 3 |
| Icon: nation | räknas **2** | räknas **1** |
| Icon: ligor | +1 till **varje** liga i laget | +1 till varje liga i laget |
| Hero: egen chemistry | alltid 3 | alltid 3 |
| Hero: liga | räknas **2** | räknas **1** |
| Hero: nation | räknas 1 | räknas 1 |
| Hall of FUT | – | som Hero |

Källor (sökning 2026-09-30): fifauteam.com FC 26/FC 27 chemistry-guider, timesaver.gg
"FC 27 Chemistry Explained", EA:s patch notes för FC 27 vid lansering (via Operation Sports
och dotesports). Tröskelvärdena för FC 27 har vi inte sett uttryckligen, men inga källor
nämner någon ändring. De antas oförändrade och bör verifieras mot spelet.

## Modellering i lösaren

För varje klubb/liga/nation *g* bland kandidaterna:
`count_g = Σ vikt_p · ipos_p`, där `ipos_p` är 1 om spelaren står i giltig position.
Nivåvariabler `b_{g,k} ⇒ count_g ≥ t_k` och `pts_g = Σ_k b_{g,k}`.
Spelarens chemistry: `chem_p ≤ 3·ipos_p` och `chem_p ≤ pts_club + pts_league + pts_nation`
(Icons/Heroes: `chem_p ≤ 3·ipos_p`).
SBC-krav på chemistry är alltid **minimikrav**, så det räcker med övre gränser. Lösaren
väljer själv att maximera där det behövs.
