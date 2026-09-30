"""Versioned chemistry rules. See docs/chemistry.md."""
from dataclasses import dataclass


@dataclass(frozen=True)
class ChemRules:
    # player counts needed for +1, +2, +3
    club: tuple[int, int, int] = (2, 4, 7)
    league: tuple[int, int, int] = (3, 5, 8)
    nation: tuple[int, int, int] = (2, 5, 8)
    icon_nation_weight: int = 1
    icon_all_leagues: int = 1
    hero_league_weight: int = 1
    hero_nation_weight: int = 1


CHEM_RULES: dict[str, ChemRules] = {
    "fc26": ChemRules(icon_nation_weight=2, hero_league_weight=2),
    "fc27": ChemRules(),
}
DEFAULT_RULESET = "fc27"


def points(count: int, thresholds: tuple[int, int, int]) -> int:
    return sum(1 for t in thresholds if count >= t)
