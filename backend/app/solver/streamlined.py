"""FC 27 Streamlined SBCs: reach an Item Score target as cheaply as possible.

Most FC 27 Player and Upgrade SBCs no longer have chemistry, position, league or squad-rating
requirements. Every submitted card is worth a fixed Item Score that depends on its OVR (and
quality); you submit cards until the target is reached. Duplicates are allowed and partial
progress is kept. Some SBCs add a minimum OVR per card.

That makes it a minimum-cost covering knapsack, solved exactly here by dynamic programming:
  * owned cards: each item at most once (0/1), cost = coin value you give up
  * market cards: any number of copies of the cheapest card per OVR (unbounded)
States are scores capped at the target, in units of the gcd of all point values.

Item Score table: post-launch values reported by allthings.how (2026-09-22) and
starcitizenguides.net (2026-09-28). EA has said special/holographic items score more than
base items of the same OVR but has not published the bonus, so they are counted at the base
value here (never more than the real score). Verify in game; the table is configurable.
"""
from dataclasses import dataclass, field
from math import gcd

import numpy as np

from .types import Card

ITEM_SCORE_FC27: dict[int, int] = {
    75: 90, 76: 100, 77: 120, 78: 140, 79: 160, 80: 180, 81: 280, 82: 340, 83: 410,
    84: 830, 85: 2_100, 86: 4_100, 87: 5_500, 88: 8_300, 89: 11_000, 90: 14_000,
    91: 19_000, 92: 20_000, 93: 25_000, 94: 30_000, 95: 40_000, 96: 55_000, 97: 85_000,
    98: 90_000, 99: 100_000,
}
BRONZE_SCORE, SILVER_SCORE = 20, 35
MAX_TARGET = 2_000_000
UNTRADEABLE_COST = 1  # untradeables have no coin value; tiny cost keeps their use minimal


def item_score(rating: int, table: dict[int, int] = ITEM_SCORE_FC27) -> int:
    if rating < 65:
        return BRONZE_SCORE
    if rating < 75:
        return SILVER_SCORE
    return table.get(min(rating, 99), 0)


@dataclass
class BuyLine:
    card: Card
    count: int


@dataclass
class StreamlinedSolution:
    status: str                         # OPTIMAL | INFEASIBLE
    message: str = ""
    target: int = 0
    points: int = 0
    total_coins: int = 0                # coins to spend on the market
    owned_value: int = 0                # coin value of tradeable owned cards submitted
    submit_owned: list[Card] = field(default_factory=list)
    buy: list[BuyLine] = field(default_factory=list)


def _owned_cost(c: Card, sell_factor: float) -> int:
    if c.untradeable:
        return UNTRADEABLE_COST
    return max(UNTRADEABLE_COST + 1, int((c.price or 0) * sell_factor))


def solve_streamlined(cards: list[Card], target: int, min_ovr: int = 0, already: int = 0,
                      use_owned: bool = True, buy_from_market: bool = True,
                      sell_factor: float = 0.95, table: dict[int, int] = ITEM_SCORE_FC27
                      ) -> StreamlinedSolution:
    """Cheapest set of cards reaching `target - already` Item Score (exact).

    sell_factor: a tradeable card you own costs what you would get for selling it
    (EA tax 5 % -> 0.95). Set lower to use your tradeable cards more readily.
    """
    need = max(0, min(target, MAX_TARGET) - already)
    if need == 0:
        return StreamlinedSolution("OPTIMAL", "Målet är redan nått.", target, already)
    eligible = [c for c in cards if c.rating >= min_ovr and item_score(c.rating, table) > 0]
    owned = [c for c in eligible if c.owned and use_owned]
    market: dict[int, Card] = {}   # cheapest buyable card per OVR
    if buy_from_market:
        for c in eligible:
            if not c.owned and c.price is not None:
                best = market.get(c.rating)
                if best is None or c.price < best.price:
                    market[c.rating] = c
    values = [item_score(c.rating, table) for c in owned] + \
             [item_score(r, table) for r in market]
    if not values:
        return StreamlinedSolution("INFEASIBLE", "Inga kort uppfyller kraven.", target, already)
    unit = 0
    for v in values + [need]:
        unit = gcd(unit, v)
    cap = -(-need // unit)                       # states 0..cap (cap = target reached)
    INF = np.iinfo(np.int64).max // 4
    dp = np.full(cap + 1, INF, dtype=np.int64)
    dp[0] = 0

    # 0/1 items (owned), vectorised: new[min(cap, s+w)] = min(old, dp[s] + cost).
    # take[i, s]: item i improved state s; cap_prev[i]: predecessor used for the capped state.
    owned_w = [item_score(c.rating, table) // unit for c in owned]
    owned_c = [_owned_cost(c, sell_factor) for c in owned]
    take = np.zeros((len(owned), cap + 1), dtype=bool)
    cap_prev = np.zeros(len(owned), dtype=np.int64)
    for i, (w, cost) in enumerate(zip(owned_w, owned_c)):
        cand = np.full(cap + 1, INF, dtype=np.int64)
        lo = max(cap - w, 0)                       # states that reach the target with item i
        if w < cap:
            cand[w:cap] = dp[:cap - w] + cost
        k = lo + int(np.argmin(dp[lo:]))
        cand[cap] = dp[k] + cost
        better = cand < dp
        take[i] = better
        cap_prev[i] = k
        dp = np.where(better, cand, dp)

    # unbounded items (market): ascending pass; a state may reuse the same OVR any number of
    # times. Updates only go upwards, so dp[s] is final when s is processed.
    mk = sorted(market.items())
    mk_w = [item_score(r, table) // unit for r, _ in mk]
    mk_c = [c.price for _, c in mk]
    par_item = np.full(cap + 1, -1, dtype=np.int64)
    par_state = np.zeros(cap + 1, dtype=np.int64)
    for st in range(cap):
        if dp[st] >= INF:
            continue
        for j, (w, cost) in enumerate(zip(mk_w, mk_c)):
            t = min(cap, st + w)
            if dp[st] + cost < dp[t]:
                dp[t] = dp[st] + cost
                par_item[t], par_state[t] = j, st
    if dp[cap] >= INF:
        return StreamlinedSolution("INFEASIBLE", "Ingen kombination når målpoängen.", target,
                                   already)

    # --- reconstruct: market purchases (applied last), then owned items backwards ---------
    counts: dict[int, int] = {}
    st = cap
    while par_item[st] >= 0:
        j = int(par_item[st])
        counts[j] = counts.get(j, 0) + 1
        st = int(par_state[st])
    chosen: list[Card] = []
    for i in range(len(owned) - 1, -1, -1):
        if st == 0:
            break
        if take[i, st]:
            chosen.append(owned[i])
            st = int(cap_prev[i]) if st == cap else st - owned_w[i]
    buy = [BuyLine(mk[j][1], n) for j, n in sorted(counts.items())]
    points = sum(item_score(c.rating, table) for c in chosen) + \
        sum(item_score(b.card.rating, table) * b.count for b in buy)
    return StreamlinedSolution(
        "OPTIMAL", "", target, already + points,
        total_coins=sum(b.card.price * b.count for b in buy),
        owned_value=sum(int((c.price or 0) * sell_factor) for c in chosen if not c.untradeable),
        submit_owned=sorted(chosen, key=lambda c: -c.rating), buy=buy)
