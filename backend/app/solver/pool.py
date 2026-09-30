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
               must_include: set[str] = frozenset()) -> list[Card]:
    if len(cards) <= opt.max_pool:
        return list(cards)
    key = lambda c: _cost_key(c, opt)  # noqa: E731
    chosen: dict[str, Card] = {c.id: c for c in cards if c.id in must_include}

    def take(bucket_fn, k):
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
            for c in matching[:60]:
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
