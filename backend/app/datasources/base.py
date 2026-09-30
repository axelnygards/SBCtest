from dataclasses import dataclass, field
from typing import Iterator, Protocol


@dataclass
class NormalizedPlayer:
    id: int                      # EA player id (= FUT resourceBaseId for base cards)
    name: str
    rating: int
    positions: list[str]         # primary first
    nation_id: int
    nation: str
    club_id: int
    club: str
    league_id: int
    league: str
    gender: int                  # 0 men, 1 women
    raw: dict = field(default_factory=dict, repr=False)


@dataclass
class League:
    id: int
    name: str
    club_ids: list[int]


class DataSource(Protocol):
    name: str
    enabled: bool

    def leagues(self) -> list[League]: ...
    def players(self) -> Iterator[NormalizedPlayer]: ...
