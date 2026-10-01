from typing import Literal

from pydantic import BaseModel, Field, field_validator

from .services import PriceOverrides
from .solver.types import Op, ReqType, Requirement


class RequirementIn(BaseModel):
    type: ReqType
    value: int
    op: Op = Op.MIN
    attr: str | None = None
    values: list[int | str] = []
    label: str = ""

    def to_domain(self) -> Requirement:
        return Requirement(self.type, self.value, self.op, self.attr, tuple(self.values), self.label)


class PricesIn(BaseModel):
    """The user's own prices: coins per rating (replaces estimates) and per card."""
    ratings: dict[int, int] = Field(default={}, max_length=60)
    cards: dict[int, int] = Field(default={}, max_length=500)

    @field_validator("ratings", "cards")
    @classmethod
    def _sane(cls, v: dict[int, int]):
        if any(not 0 <= coins <= 15_000_000 for coins in v.values()):
            raise ValueError("priset måste vara 0–15 000 000")
        return v

    def to_domain(self) -> PriceOverrides:
        return PriceOverrides(dict(self.ratings), dict(self.cards))


class SolveIn(BaseModel):
    formation: str = "4-4-2"
    requirements: list[RequirementIn]
    use_club: bool = True
    only_club: bool = False
    buy_from_market: bool = True
    time_limit_s: float = Field(20, gt=0, le=30)
    alternatives: int = Field(0, ge=0, le=5)
    excluded_ids: list[str] = Field(default=[], max_length=500)
    locked: dict[int, str] = {}
    owned_cost_factor: float = Field(0.95, ge=0, le=1)  # sale value of own tradeable cards
    untradeable_bonus: int = Field(0, ge=0, le=100_000)
    prices: PricesIn | None = None
    platform: Literal["console", "pc"] | None = None   # without an account (else the account's)


class CardView(BaseModel):
    card_name: str | None = None
    stats: dict[str, int] = {}
    rarity: str = "unknown"
    kind: str = "normal"
    positions: list[str] = []
    nation: str | None = None
    club: str | None = None
    league: str | None = None
    face: str | None = None
    flag: str | None = None
    badge: str | None = None


class SlotOut(CardView):
    slot: int
    position: str
    card_id: str
    definition_id: int | None
    name: str
    rating: int
    in_position: bool
    chemistry: int
    owned: bool
    untradeable: bool
    price: int | None
    price_source: str | None          # live | estimate | default | None
    price_age_min: int | None


class SolutionOut(BaseModel):
    status: str
    message: str
    total_cost: int
    team_rating: int
    team_chem: int
    slots: list[SlotOut]
    violations: list[str]
    pool_size: int
    wall_time_s: float
    estimated_cost_share: float       # share of coins based on non-live prices
    owned_value: int = 0              # sale value of own TRADEABLE cards the squad uses
    requirements: list[dict] = []     # per request requirement: {"ok": bool, "actual": int}
    own_cost_share: float = 0.0       # share of coins based on the user's own prices
    cached_age_s: int | None = None   # served from the shared cache, computed this long ago


class UserCreateIn(BaseModel):
    platform: Literal["console", "pc"] = "console"


class UserOut(BaseModel):
    user_id: str
    token: str | None = None
    platform: str
    club_size: int = 0
    club_imported_at: str | None = None


class ClubImportIn(BaseModel):
    items: list[dict] = Field(max_length=6000)
    location: Literal["club", "storage", "unassigned"] = "club"
    replace: bool = True


class PriceRowIn(BaseModel):
    definition_id: int
    kind: Literal["bin_min", "sold", "limit_min", "limit_max"]
    price: int
    sample_size: int = 1


class ObservationsIn(BaseModel):
    platform: Literal["console", "pc"] | None = None
    items: list[dict] = Field(default=[], max_length=2000)   # itemData seen (learn rarity)
    prices: list[PriceRowIn] = Field(default=[], max_length=2000)


class StreamlinedIn(BaseModel):
    target: int = Field(gt=0, le=2_000_000)
    min_ovr: int = Field(0, ge=0, le=99)
    already: int = Field(0, ge=0)
    use_club: bool = True
    buy_from_market: bool = True
    sell_factor: float = Field(0.95, ge=0, le=1)
    prices: PricesIn | None = None
    platform: Literal["console", "pc"] | None = None
    excluded_ids: list[str] = Field(default=[], max_length=500)


class StreamlinedCardOut(CardView):
    card_id: str
    definition_id: int | None
    name: str
    rating: int
    points: int
    count: int = 1
    owned: bool
    untradeable: bool
    price: int | None
    price_source: str | None = None
    price_age_min: int | None = None


class StreamlinedOut(BaseModel):
    status: str
    message: str
    target: int
    points: int
    total_coins: int
    owned_value: int
    submit: list[StreamlinedCardOut]
    buy: list[StreamlinedCardOut]
    estimated_cost_share: float
    own_cost_share: float = 0.0


class PriceReportIn(BaseModel):
    """In-app price reports: what cards cost in the game right now, and fodder per rating."""
    platform: Literal["console", "pc"] = "console"
    cards: dict[int, int] = Field(default={}, max_length=50)
    ratings: dict[int, int] = Field(default={}, max_length=60)
