import itertools
import random

from app.solver.streamlined import (ITEM_SCORE_FC27, UNTRADEABLE_COST, item_score,
                                    solve_streamlined)

from .factory import card


def total_points(sol):
    return sum(item_score(c.rating) for c in sol.submit_owned) + \
        sum(item_score(b.card.rating) * b.count for b in sol.buy)


def cost(sol, sell=0.95):
    owned = sum(UNTRADEABLE_COST if c.untradeable else max(UNTRADEABLE_COST + 1, int(c.price * sell))
                for c in sol.submit_owned)
    return sol.total_coins + owned


def brute(owned, market, target, sell=0.95):
    """Exhaustive: every subset of owned x up to 30 copies of each market card."""
    best = None
    for k in range(len(owned) + 1):
        for sub in itertools.combinations(owned, k):
            pts = sum(item_score(c.rating) for c in sub)
            oc = sum(UNTRADEABLE_COST if c.untradeable else max(UNTRADEABLE_COST + 1, int(c.price * sell))
                     for c in sub)
            # market: min cost to cover the remainder with unbounded copies (small DP)
            need = max(0, target - pts)
            dp = {0: 0}
            for s in range(0, need + 1, 5):
                if s not in dp:
                    continue
                for m in market:
                    t = min(need, s + item_score(m.rating))
                    if dp[s] + m.price < dp.get(t, 10**18):
                        dp[t] = dp[s] + m.price
            if need in dp:
                c = oc + dp[need]
                best = c if best is None or c < best else best
    return best


def test_score_table():
    assert item_score(50) == 20 and item_score(70) == 35
    assert item_score(83) == 410 and item_score(85) == 2100 and item_score(99) == 100_000
    assert all(ITEM_SCORE_FC27[r] <= ITEM_SCORE_FC27[r + 1] for r in range(75, 99))


def test_matches_brute_force():
    rng = random.Random(11)
    for _ in range(25):
        owned = [card(i, rng.randint(70, 86), price=rng.randint(3, 60) * 100, owned=True,
                      untradeable=rng.random() < 0.4) for i in range(rng.randint(0, 6))]
        market = [card(100 + i, r, price=rng.randint(3, 400) * 100)
                  for i, r in enumerate(rng.sample(range(74, 88), 5))]
        target = rng.choice([500, 1200, 2500, 4000])
        sol = solve_streamlined(owned + market, target)
        assert sol.status == "OPTIMAL"
        assert total_points(sol) >= target
        assert cost(sol) == brute(owned, market, target)


def test_83_upgrade_uses_untradeables_first():
    owned = [card(i, 84, price=5000, owned=True, untradeable=True) for i in range(3)]
    market = [card(10 + r, r, price=p) for r, p in ((83, 1500), (84, 2600), (85, 9000))]
    sol = solve_streamlined(owned + market, 2500)
    assert total_points(sol) >= 2500
    assert len(sol.submit_owned) == 3                    # 3 x 830 = 2490 from the club ...
    assert sol.total_coins == 1500                       # ... + one 83 bought
    assert [(b.card.rating, b.count) for b in sol.buy] == [(83, 1)]


def test_min_ovr_and_already():
    cards = [card(1, 80, price=400), card(2, 84, price=2600)]
    sol = solve_streamlined(cards, 2500, min_ovr=84)
    assert all(b.card.rating >= 84 for b in sol.buy) and sol.total_coins == 4 * 2600
    sol = solve_streamlined(cards, 2500, min_ovr=84, already=2000)
    assert sol.total_coins == 2600 and sol.points >= 2500


def test_infeasible_and_done():
    assert solve_streamlined([card(1, 70, price=300, owned=True)], 1000,
                             buy_from_market=False).status == "INFEASIBLE"
    assert solve_streamlined([], 500, already=600).status == "OPTIMAL"


def test_large_target_is_fast():
    from .factory import Timer, universe
    uni = universe(seed=9)
    owned = [card(10**6 + i, 70 + i % 18, price=1000, owned=True, untradeable=i % 2 == 0)
             for i in range(1500)]
    with Timer() as t:
        sol = solve_streamlined(uni + owned, 20_000)
    assert sol.status == "OPTIMAL" and total_points(sol) >= 20_000
    assert t.s < 5
