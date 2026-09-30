"""Hash indexes over a card list, built once in O(N).

Every lookup the model builder and pool pruning need is a dict access, never a scan:
  by_id[id] -> position in cards      by_base[base_id] -> [positions]
  by_nation / by_league / by_club / by_rating / by_position[key] -> [positions]
Positions (ints) index into `cards`, which is sorted by cost, so every bucket is too.
"""
from collections import defaultdict
from dataclasses import dataclass, field

from .types import Card


@dataclass
class CardIndex:
    cards: list[Card]
    by_id: dict[str, int] = field(default_factory=dict)
    by_base: dict[int, list[int]] = field(default_factory=lambda: defaultdict(list))
    by_nation: dict[int, list[int]] = field(default_factory=lambda: defaultdict(list))
    by_league: dict[int, list[int]] = field(default_factory=lambda: defaultdict(list))
    by_club: dict[int, list[int]] = field(default_factory=lambda: defaultdict(list))
    by_rating: dict[int, list[int]] = field(default_factory=lambda: defaultdict(list))
    by_position: dict[str, list[int]] = field(default_factory=lambda: defaultdict(list))

    @classmethod
    def build(cls, cards: list[Card]) -> "CardIndex":
        ix = cls(cards)
        for i, c in enumerate(cards):
            ix.by_id[c.id] = i
            ix.by_base[c.base_id].append(i)
            ix.by_nation[c.nation].append(i)
            ix.by_league[c.league].append(i)
            ix.by_club[c.club].append(i)
            ix.by_rating[c.rating].append(i)
            for pos in c.positions:
                ix.by_position[pos].append(i)
        return ix

    def bucket(self, attr: str) -> dict:
        return {"nation": self.by_nation, "league": self.by_league, "club": self.by_club,
                "rating": self.by_rating}[attr]
