from dataclasses import dataclass, field
from enum import Enum


class CardKind(str, Enum):
    NORMAL = "normal"
    ICON = "icon"
    HERO = "hero"  # also Hall of FUT in fc27


@dataclass(frozen=True)
class Card:
    id: str                       # unique card id (club item id or definition id)
    base_id: int                  # same real player -> same base_id (no duplicates allowed)
    name: str
    rating: int
    positions: tuple[str, ...]
    nation: int
    league: int
    club: int
    rarity: str = "common"        # common | rare | special rarity name (totw, ...)
    kind: CardKind = CardKind.NORMAL
    owned: bool = False
    untradeable: bool = False
    price: int | None = None      # market price in coins, None = unknown

    @property
    def quality(self) -> str:
        if self.rating >= 75:
            return "gold"
        if self.rating >= 65:
            return "silver"
        return "bronze"

    @property
    def is_rare(self) -> bool:
        return self.rarity != "common"

    @property
    def is_special(self) -> bool:
        return self.rarity not in ("common", "rare")


class ReqType(str, Enum):
    TEAM_RATING = "team_rating"   # min team rating
    TEAM_CHEM = "team_chem"       # min total chemistry
    PLAYER_CHEM = "player_chem"   # min chemistry for every player
    COUNT = "count"               # number of players whose attr is in values
    SAME = "same"                 # players from the same attr group (min: some group, max: every group)
    DISTINCT = "distinct"         # number of distinct attr groups


class Op(str, Enum):
    MIN = "min"
    MAX = "max"
    EXACT = "exact"


# attributes usable in COUNT / SAME / DISTINCT
ATTRS = ("nation", "league", "club", "rarity", "quality", "rare", "special", "rating_gte", "kind")


@dataclass(frozen=True)
class Requirement:
    type: ReqType
    value: int
    op: Op = Op.MIN
    attr: str | None = None
    values: tuple = ()
    label: str = ""

    def matches(self, card: Card) -> bool:
        """For COUNT requirements: does this card count?"""
        a = self.attr
        if a == "rating_gte":
            return card.rating >= self.values[0]
        if a == "rare":
            return card.is_rare
        if a == "special":
            return card.is_special
        if a == "quality":
            return card.quality in self.values
        if a == "kind":
            return card.kind.value in self.values
        return getattr(card, a) in self.values


@dataclass
class SolveOptions:
    formation: str = "4-4-2"
    ruleset: str = "fc27"
    use_owned: bool = True
    only_owned: bool = False
    owned_cost_factor: float = 0.95    # owned tradeable card costs what selling it would give
                                       # (market price minus EA's 5 % tax); untradeables cost 0
    untradeable_bonus: int = 0         # extra coins subtracted for using untradeables (prefer them)
    time_limit_s: float = 20.0
    max_pool: int = 1500
    excluded_ids: frozenset[str] = frozenset()
    locked: dict[int, str] = field(default_factory=dict)  # slot index -> card id
    alternatives: int = 0              # extra distinct solutions to return


@dataclass
class SlotAssignment:
    slot: int
    position: str
    card: Card
    in_position: bool
    chemistry: int


@dataclass
class Solution:
    status: str                        # OPTIMAL | FEASIBLE | INFEASIBLE | UNKNOWN
    slots: list[SlotAssignment] = field(default_factory=list)
    total_cost: int = 0
    team_rating: int = 0
    team_chem: int = 0
    violations: list[str] = field(default_factory=list)
    message: str = ""
    pool_size: int = 0
    wall_time_s: float = 0.0
