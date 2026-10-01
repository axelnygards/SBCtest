"""Fast constructive squads used as the first incumbent for CP-SAT.

CP-SAT's lower bounds for chemistry SBCs are strong, but finding a first squad with high
chemistry can take longer than the whole time limit. A squad built from ONE league, nation
or club, all in position, already has high chemistry (8+ from one league = +3 league each).
So: for the most promising groups and a few rating floors, fill every slot with the
cheapest in-position card of the group, and keep the squads the independent checker accepts.
"""
from collections import defaultdict

from .evaluate import check
from .types import Card, ReqType, Requirement, SolveOptions


def _fill(group: list[Card], positions: tuple[str, ...], floor: int, cost) -> list[Card] | None:
    by_pos = defaultdict(list)
    for c in sorted(group, key=cost):
        if c.rating >= floor:
            for p in c.positions:
                by_pos[p].append(c)
    used, squad = set(), [None] * len(positions)
    # scarcest positions first so a versatile cheap card is not wasted on an easy slot
    for s in sorted(range(len(positions)), key=lambda s: len(by_pos[positions[s]])):
        pick = next((c for c in by_pos[positions[s]] if c.base_id not in used), None)
        if pick is None:
            return None
        used.add(pick.base_id)
        squad[s] = pick
    return squad


def greedy_squads(cards: list[Card], reqs: list[Requirement], opt: SolveOptions,
                  positions: tuple[str, ...], cost, max_groups: int = 12,
                  limit: int = 5) -> list[list[Card]]:
    """Up to `limit` valid squads (cheapest first), each in slot order."""
    if opt.locked:
        return []  # keep it simple: locked slots are left to CP-SAT
    target = max((r.value for r in reqs if r.type == ReqType.TEAM_RATING), default=0)
    floors = sorted({max(target - 1, 0), target, target + 1}) if target else [0]
    named = defaultdict(set)
    for r in reqs:
        if r.type == ReqType.COUNT and r.attr in ("league", "nation", "club"):
            named[r.attr].update(r.values)
    out: dict[frozenset, list[Card]] = {}
    for attr in ("league", "nation", "club"):
        groups = defaultdict(list)
        for c in cards:
            groups[getattr(c, attr)].append(c)
        # groups that can field a full in-position squad, cheapest first
        scored = []
        for g, cs in groups.items():
            if len(cs) < len(positions):
                continue
            sq = _fill(cs, positions, floors[0], cost)
            if sq is not None:
                scored.append((sum(cost(c) for c in sq), g))
        scored.sort()
        picks = [g for _, g in scored[:max_groups]] + [g for g in named[attr] if g in groups]
        for g in dict.fromkeys(picks):
            for floor in floors:
                sq = _fill(groups[g], positions, floor, cost)
                if sq is not None and not check(positions, sq, reqs, opt.ruleset):
                    out.setdefault(frozenset(c.id for c in sq), sq)
    return sorted(out.values(), key=lambda sq: sum(cost(c) for c in sq))[:limit]
