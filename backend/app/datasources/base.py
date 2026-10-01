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
    avatar_url: str = ""         # EA portrait ("game face")
    nation_img: str = ""
    club_img: str = ""
    card_name: str = ""          # name as printed on the card (common name or last name)
    face_stats: dict = field(default_factory=dict)  # the six card stats, e.g. {"PAC": 97, ...}
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
