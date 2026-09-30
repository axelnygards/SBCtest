"""Independent, straightforward evaluation of a squad. Used to verify solver output."""
from collections import Counter

from .rating import team_rating
from .rules import CHEM_RULES, ChemRules, points
from .types import Card, CardKind, Op, ReqType, Requirement


def _group_counts(placed: list[tuple[Card, bool]], rules: ChemRules):
    club, league, nation = Counter(), Counter(), Counter()
    icons_in_pos = 0
    for card, ipos in placed:
        if not ipos:
            continue
        if card.kind == CardKind.ICON:
            nation[card.nation] += rules.icon_nation_weight
            icons_in_pos += 1
        elif card.kind == CardKind.HERO:
            nation[card.nation] += rules.hero_nation_weight
            league[card.league] += rules.hero_league_weight
        else:
            club[card.club] += 1
            league[card.league] += 1
            nation[card.nation] += 1
    if icons_in_pos:
        for g in list(league):
            league[g] += icons_in_pos * rules.icon_all_leagues
    return club, league, nation, icons_in_pos


def chemistry(positions: tuple[str, ...], cards: list[Card], ruleset: str = "fc27") -> list[int]:
    rules = CHEM_RULES[ruleset]
    placed = [(c, pos in c.positions) for pos, c in zip(positions, cards)]
    club, league, nation, _ = _group_counts(placed, rules)
    out = []
    for card, ipos in placed:
        if not ipos:
            out.append(0)
        elif card.kind in (CardKind.ICON, CardKind.HERO):
            out.append(3)
        else:
            pts = (points(club[card.club], rules.club) + points(league[card.league], rules.league)
                   + points(nation[card.nation], rules.nation))
            out.append(min(3, pts))
    return out


def _attr_key(card: Card, attr: str):
    if attr == "quality":
        return card.quality
    return getattr(card, attr)


def check(positions, cards: list[Card], reqs: list[Requirement], ruleset: str = "fc27") -> list[str]:
    """Return a list of human-readable violations (empty = valid)."""
    v = []
    if len({c.base_id for c in cards}) != len(cards):
        v.append("duplicate player")
    chem = chemistry(positions, cards, ruleset)
    for r in reqs:
        if r.type == ReqType.TEAM_RATING:
            tr = team_rating([c.rating for c in cards])
            if tr < r.value:
                v.append(f"team rating {tr} < {r.value}")
        elif r.type == ReqType.TEAM_CHEM:
            if sum(chem) < r.value:
                v.append(f"team chem {sum(chem)} < {r.value}")
        elif r.type == ReqType.PLAYER_CHEM:
            if min(chem) < r.value:
                v.append(f"player chem {min(chem)} < {r.value}")
        elif r.type == ReqType.COUNT:
            n = sum(1 for c in cards if r.matches(c))
            if not _cmp(n, r):
                v.append(f"count {r.attr}{list(r.values)}={n} not {r.op.value} {r.value}")
        elif r.type == ReqType.SAME:
            counts = Counter(_attr_key(c, r.attr) for c in cards)
            best = max(counts.values())
            if r.op == Op.MIN and best < r.value or r.op == Op.MAX and best > r.value \
                    or r.op == Op.EXACT and best != r.value:
                v.append(f"same {r.attr}={best} not {r.op.value} {r.value}")
        elif r.type == ReqType.DISTINCT:
            n = len({_attr_key(c, r.attr) for c in cards})
            if not _cmp(n, r):
                v.append(f"distinct {r.attr}={n} not {r.op.value} {r.value}")
    return v


def _cmp(n: int, r: Requirement) -> bool:
    return n >= r.value if r.op == Op.MIN else n <= r.value if r.op == Op.MAX else n == r.value
