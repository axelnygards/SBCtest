"""Candidate pool pruning.

The full player universe (~17k base cards plus specials) is too large for a quick exact model.
We keep the cheapest few cards in several buckets, so the pool still contains every card that
could plausibly be part of a cheapest solution. The solution is optimal *within the pool*;
raise SolveOptions.max_pool (or call solve(prune=False)) to widen it.
"""
from collections import defaultdict

from .types import Card, ReqType, Requirement, SolveOptions


def _cost_key(c: Card, opt: SolveOptions):
    from .cpsat import card_cost
    return (card_cost(c, opt), c.rating)


def build_pool(cards: list[Card], reqs: list[Requirement], opt: SolveOptions,
               must_include: set[str] = frozenset(), scale: float = 1.0) -> list[Card]:
    """scale < 1 builds a smaller pool of the very cheapest cards (used for the warm start)."""
    if len(cards) <= opt.max_pool:
        return list(cards)
    key = lambda c: _cost_key(c, opt)  # noqa: E731
    chosen: dict[str, Card] = {c.id: c for c in cards if c.id in must_include}

    def take(bucket_fn, k):
        k = max(1, int(k * scale))
        buckets = defaultdict(list)
        for c in cards:
            buckets[bucket_fn(c)].append(c)
        for b in buckets.values():
            b.sort(key=key)
            for c in b[:k]:
                chosen.setdefault(c.id, c)

    needs_chem = any(r.type in (ReqType.TEAM_CHEM, ReqType.PLAYER_CHEM) and r.value > 0
                     for r in reqs)
    # cheapest per rating (drives team-rating solutions)
    take(lambda c: c.rating, 15)
    # cheapest per rating & position family, so every slot can be filled in position
    take(lambda c: (c.rating, c.positions[0] if c.positions else ""), 2)
    if needs_chem:
        take(lambda c: (c.rating // 3, c.league), 3)
        take(lambda c: (c.rating // 4, c.nation), 2)
        take(lambda c: (c.rating // 5, c.club), 2)
    # anything named explicitly by a requirement
    for r in reqs:
        if r.type == ReqType.COUNT:
            matching = sorted((c for c in cards if r.matches(c)), key=key)
            for c in matching[:max(5, int(60 * scale))]:
                chosen.setdefault(c.id, c)
    # owned cards are (nearly) free: keep the cheapest ones per rating
    take(lambda c: (c.owned, c.rating, c.league) if c.owned else None, 6)

    # Never truncate globally by cost: that would drop every high-rated card. The bucket sizes
    # above bound the pool (~45 ratings x ~25 + position/chem buckets); max_pool is a soft cap
    # that only trims the most expensive card *within* over-full ratings.
    pool = sorted(chosen.values(), key=key)
    if len(pool) > opt.max_pool:
        per_rating = defaultdict(list)
        for c in pool:
            per_rating[c.rating].append(c)
        cap = max(opt.max_pool // max(len(per_rating), 1), 12)
        pool = [c for cs in per_rating.values() for c in cs[:cap]]
        pool += [c for c in chosen.values() if c.id in must_include and c not in pool]
    return pool


def _fill_cost(group: list[Card], positions: tuple[str, ...], key) -> tuple[int, float]:
    """(missing slots, coins) to fill the formation in position with the cheapest group cards."""
    used, coins, missing = set(), 0.0, 0
    by_pos = defaultdict(list)
    for c in sorted(group, key=key):
        for p in c.positions:
            by_pos[p].append(c)
    # scarcest positions first so a versatile cheap card is not wasted on an easy slot
    for pos in sorted(positions, key=lambda p: len(by_pos[p])):
        pick = next((c for c in by_pos[pos] if c.base_id not in used), None)
        if pick is None:
            missing += 1
        else:
            used.add(pick.base_id)
            coins += key(pick)[0]
    return missing, coins


def chem_pool(cards: list[Card], reqs: list[Requirement], opt: SolveOptions,
              positions: tuple[str, ...], must_include: set[str] = frozenset(),
              n_groups: int = 8, per_pos: int = 3) -> list[Card]:
    """A small pool for chemistry: cheap chemistry comes from FEW groups with MANY cheap
    players (11 from one league = 33 chem), not from the globally cheapest cards that are
    spread over hundreds of clubs. Ranks leagues/nations/clubs by what it costs to fill the
    formation in position from that group alone and keeps the cheapest players per position
    of the best groups, plus every group a requirement names explicitly."""
    key = lambda c: _cost_key(c, opt)  # noqa: E731
    target = max((r.value for r in reqs if r.type == ReqType.TEAM_RATING), default=None)
    named = defaultdict(set)
    for r in reqs:
        if r.type == ReqType.COUNT and r.attr in ("league", "nation", "club"):
            named[r.attr].update(r.values)
    chosen: dict[str, Card] = {c.id: c for c in cards if c.id in must_include}
    pos_types = set(positions)

    def add_group(group: list[Card]):
        by_pos = defaultdict(list)
        for c in group:
            for p in c.positions:
                if p in pos_types:
                    by_pos[p].append(c)
        for cs in by_pos.values():
            cs.sort(key=key)
            picks = cs[:per_pos]
            if target is not None:
                picks += [c for c in cs if c.rating >= target - 2][:2]
            for c in picks:
                chosen.setdefault(c.id, c)

    for attr in ("league", "nation", "club"):
        groups = defaultdict(list)
        for c in cards:
            groups[getattr(c, attr)].append(c)
        ranked = sorted(groups, key=lambda g: _fill_cost(groups[g], positions, key))
        for g in ranked[:n_groups] + [g for g in named[attr] if g in groups]:
            add_group(groups[g])
    add_group(cards)  # global cheapest fillers per position
    return list(chosen.values())
