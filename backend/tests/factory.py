"""Synthetic but realistic card universe for tests (EA data is not reachable in CI)."""
import random
import time

from app.solver.types import Card, CardKind

POSITIONS = ["GK", "RB", "LB", "CB", "CDM", "CM", "CAM", "RM", "LM", "RW", "LW", "ST"]
ALT = {"RB": ["RWB", "RM"], "LB": ["LWB", "LM"], "CB": ["CDM"], "CDM": ["CM", "CB"],
       "CM": ["CDM", "CAM"], "CAM": ["CM", "ST"], "RM": ["RW", "RB"], "LM": ["LW", "LB"],
       "RW": ["RM", "ST"], "LW": ["LM", "ST"], "ST": ["CAM"], "GK": []}


def price_for(rating: int, rng: random.Random) -> int:
    base = 200 if rating < 75 else 350 if rating < 82 else int(700 * 1.55 ** (rating - 82))
    return int(base * rng.uniform(0.8, 1.6)) // 50 * 50 + 50


def card(i, rating, pos=("ST",), nation=1, league=1, club=1, price=1000, **kw) -> Card:
    return Card(id=str(i), base_id=kw.pop("base_id", i), name=f"P{i}", rating=rating,
                positions=tuple(pos), nation=nation, league=league, club=club, price=price, **kw)


def universe(n=3000, seed=1, n_leagues=12, clubs_per_league=16, n_nations=40,
             icons=20, heroes=20) -> list[Card]:
    rng = random.Random(seed)
    cards = []
    for i in range(n):
        rating = max(50, min(95, int(rng.gauss(74, 7))))
        league = rng.randrange(n_leagues)
        club = league * 100 + rng.randrange(clubs_per_league)
        nation = min(int(rng.expovariate(1 / 8)), n_nations - 1)
        p = rng.choice(POSITIONS)
        pos = (p, *rng.sample(ALT[p], k=min(len(ALT[p]), rng.randrange(3))))
        rarity = "rare" if rng.random() < 0.45 else "common"
        if rating >= 83 and rng.random() < 0.15:
            rarity = "totw"
        cards.append(Card(str(i), i, f"P{i}", rating, pos, nation, league, club, rarity,
                          price=price_for(rating, rng) * (3 if rarity == "totw" else 1)))
    for j in range(icons):
        i = n + j
        p = rng.choice(POSITIONS[1:])
        cards.append(Card(str(i), i, f"Icon{j}", rng.randint(86, 93), (p,),
                          rng.randrange(n_nations), 2118, 112658, "icon", CardKind.ICON,
                          price=rng.randint(200_000, 900_000)))
    for j in range(heroes):
        i = n + icons + j
        p = rng.choice(POSITIONS[1:])
        cards.append(Card(str(i), i, f"Hero{j}", rng.randint(85, 90), (p,),
                          rng.randrange(n_nations), rng.randrange(n_leagues), 99999, "hero",
                          CardKind.HERO, price=rng.randint(80_000, 300_000)))
    return cards


class Timer:
    def __enter__(self):
        self.t = time.monotonic()
        return self

    def __exit__(self, *a):
        self.s = time.monotonic() - self.t
