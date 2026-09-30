# Lagbetyg (Team Rating)

Formeln är härledd av communityn och har varit stabil sedan FIFA 17. För SBC:er räknas bara
de spelare som ingår i SBC-truppen, normalt 11 (bänk saknas).

```
n     = antal spelare (11 i SBC)
S     = Σ betyg
avg   = S / n                         (ingen avrundning)
E     = Σ max(betyg_i − avg, 0)       (korrektionsfaktor, ingen avrundning)
total = round_half_up(S + E)
TR    = floor(total / n)
```

## Exakt heltalsform (används i CP-SAT)

`TR ≥ T` ⇔ `S + E ≥ n·T − 0.5` ⇔ `n·S + Σ max(n·betyg_i − S, 0) ≥ n²·T − n/2`.
Vänsterledet är ett heltal, så villkoret blir
`n·S + Σ e_i ≥ n²·T − floor(n/2)`, där `e_i = max(n·betyg_i − S, 0)`.
Lösaren har `S` som heltalsvariabel, `e_i` via `AddMaxEquality` och multiplicerar med
valvariabeln genom övre gränser (villkoret är ett minimikrav).

## Verifierade exempel (se `backend/tests/test_rating.py`)

| Trupp | S | E | total | TR |
|---|---|---|---|---|
| 11×84 | 924 | 0 | 924 | **84** |
| 10×83 + 1×84 | 914 | 0,909 | 915 | **83** |
| 2×85, 7×84, 2×83 | 924 | 2 | 926 | **84** |
| 1×90, 10×83 | 920 | 6,36 | 926 | **84** |
| 3×86, 8×82 | 914 | 8,73 | 923 | **83** |
| 3×87, 8×82 | 917 | 10,91 | 928 | **84** |

Rad 4 och 6 visar varför formeln behövs: snittet är 83,6 respektive 83,4, men korrektionen
lyfter laget till 84. Rad 5 missar precis. Det är så "billiga" SBC-lösningar med en hög spelare och resten låga
fungerar. Implementationen testas mot både den direkta formeln och CP-SAT-varianten
(egenskapstest på slumpade trupper).
