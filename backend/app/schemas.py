from typing import Literal

from pydantic import BaseModel, Field

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


class SolveIn(BaseModel):
    formation: str = "4-4-2"
    requirements: list[RequirementIn]
    use_club: bool = True
    only_club: bool = False
    buy_from_market: bool = True
    time_limit_s: float = Field(20, gt=0, le=30)
    alternatives: int = Field(0, ge=0, le=5)
    excluded_ids: list[str] = []
    locked: dict[int, str] = {}
    owned_cost_factor: float = Field(0.0, ge=0, le=1)
    untradeable_bonus: int = Field(0, ge=0, le=100_000)


class SlotOut(BaseModel):
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
    kind: Literal["bin_min", "limit_min", "limit_max"]
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


class StreamlinedCardOut(BaseModel):
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
