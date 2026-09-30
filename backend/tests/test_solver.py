import itertools
import random

import pytest

from app.solver.cpsat import MAX_TIME_S, solve
from app.solver.evaluate import check
from app.solver.formations import slots_for
from app.solver.index import CardIndex
from app.solver.types import Op, ReqType, Requirement as R, SolveOptions

from .factory import Timer, card, universe

F442 = slots_for("4-4-2")


@pytest.fixture(scope="module")
def uni():
    return universe()


def assert_valid(sol, reqs, opt=None):
    opt = opt or SolveOptions()
    assert sol.status in ("OPTIMAL", "FEASIBLE"), sol.message
    assert len(sol.slots) == 11
    cards = [a.card for a in sol.slots]
    assert check(slots_for(opt.formation), cards, reqs, opt.ruleset) == []
    assert sol.violations == []


# ---- optimality against brute force on small pools ---------------------------

def brute_force(cards, reqs, n=11):
    best = None
    for combo in itertools.combinations(cards, n):
        if check(F442, list(combo), reqs):  # positions irrelevant without chem reqs
            continue
        cost = sum(c.price for c in combo)
        best = cost if best is None or cost < best else best
    return best


@pytest.mark.parametrize("seed", range(6))
def test_matches_brute_force_rating(seed):
    rng = random.Random(seed)
    cards = [card(i, rng.randint(78, 88), nation=rng.randrange(3), league=rng.randrange(3),
                  price=rng.randint(5, 60) * 100) for i in range(16)]
    reqs = [R(ReqType.TEAM_RATING, 83),
            R(ReqType.COUNT, 2, Op.MIN, "nation", (0,)),
            R(ReqType.DISTINCT, 2, Op.MAX, "league")]
    expected = brute_force(cards, reqs)
    sol = solve(cards, reqs, prune=False)[0]
    if expected is None:
        assert sol.status == "INFEASIBLE" and sol.message
    else:
        assert_valid(sol, reqs)
        assert sol.total_cost == expected


# ---- realistic SBCs on a 3000-card universe --------------------------------------

SBCS = {
    "84 rated": [R(ReqType.TEAM_RATING, 84)],
    "86 rated + 1 TOTW": [R(ReqType.TEAM_RATING, 86), R(ReqType.COUNT, 1, Op.MIN, "rarity", ("totw",))],
    "League & nation": [R(ReqType.TEAM_RATING, 80), R(ReqType.TEAM_CHEM, 20),
                        R(ReqType.COUNT, 3, Op.MIN, "league", (2,)),
                        R(ReqType.DISTINCT, 4, Op.MIN, "nation")],
    "Hybrid leagues": [R(ReqType.TEAM_RATING, 78), R(ReqType.DISTINCT, 5, Op.MIN, "league"),
                       R(ReqType.SAME, 3, Op.MAX, "league"), R(ReqType.TEAM_CHEM, 15)],
    "Max chem": [R(ReqType.TEAM_CHEM, 33)],
    "Player chem 1": [R(ReqType.PLAYER_CHEM, 1), R(ReqType.TEAM_RATING, 81)],
    "Silver rares": [R(ReqType.COUNT, 11, Op.EXACT, "quality", ("silver",)),
                     R(ReqType.COUNT, 5, Op.MIN, "rare"), R(ReqType.SAME, 4, Op.MIN, "club")],
}


@pytest.mark.parametrize("name", SBCS)
def test_realistic_sbcs(uni, name):
    reqs = SBCS[name]
    with Timer() as t:
        sol = solve(uni, reqs, SolveOptions(time_limit_s=15))[0]
    assert_valid(sol, reqs)
    assert t.s < MAX_TIME_S


def test_pool_pruning_does_not_hurt_much(uni):
    reqs = [R(ReqType.TEAM_RATING, 84)]
    pruned = solve(uni, reqs)[0]
    full = solve(uni, reqs, SolveOptions(time_limit_s=25), prune=False)[0]
    assert pruned.total_cost <= full.total_cost * 1.02


# ---- behaviour & guarantees ------------------------------------------------------

def test_no_duplicate_players():
    cards = [card(i, 90, base_id=1, price=100) for i in range(5)]  # 5 versions of one player
    cards += [card(10 + i, 70, price=1000) for i in range(10)]
    sol = solve(cards, [], prune=False)[0]
    assert sum(1 for a in sol.slots if a.card.base_id == 1) == 1


def test_infeasible_reports_message():
    cards = [card(i, 70, price=100) for i in range(20)]
    sol = solve(cards, [R(ReqType.TEAM_RATING, 85)])[0]
    assert sol.status == "INFEASIBLE"
    assert "Ingen lösning" in sol.message


def test_too_few_cards():
    sol = solve([card(i, 80) for i in range(5)], [])[0]
    assert sol.status == "INFEASIBLE"


def test_circuit_breaker_time_limit(uni):
    # hard, likely infeasible: 33 chem, 90 rated, 11 distinct nations
    reqs = [R(ReqType.TEAM_CHEM, 33), R(ReqType.TEAM_RATING, 90),
            R(ReqType.DISTINCT, 11, Op.MIN, "nation")]
    with Timer() as t:
        sol = solve(uni, reqs, SolveOptions(time_limit_s=2, max_pool=2000))[0]
    assert t.s < 2 + 5  # deadline + model build
    assert sol.status in ("INFEASIBLE", "UNKNOWN") and sol.message


def test_time_limit_is_clamped(uni):
    opt = SolveOptions(time_limit_s=10_000, alternatives=100)
    with Timer() as t:
        solve(uni, [R(ReqType.TEAM_RATING, 83)], opt)
    assert t.s < MAX_TIME_S + 5


def test_owned_cards_are_used_first(uni):
    owned = [card(900_000 + i, 84, pos=(p,), price=5000, owned=True, untradeable=True)
             for i, p in enumerate(F442)]
    sol = solve(uni + owned, [R(ReqType.TEAM_RATING, 84)])[0]
    assert sol.total_cost == 0 and all(a.card.owned for a in sol.slots)


def test_only_owned(uni):
    owned = [card(900_000 + i, 70 + i, pos=(p,), owned=True) for i, p in enumerate(F442)]
    sol = solve(uni + owned, [], SolveOptions(only_owned=True))[0]
    assert all(a.card.owned for a in sol.slots)


def test_locked_and_excluded(uni):
    reqs = [R(ReqType.TEAM_RATING, 84), R(ReqType.TEAM_CHEM, 20)]
    first = solve(uni, reqs)[0]
    lock_card = max(uni, key=lambda c: c.rating if "ST" in c.positions else 0)
    banned = first.slots[3].card.id
    opt = SolveOptions(locked={10: lock_card.id}, excluded_ids=frozenset({banned}))
    sol = solve(uni, reqs, opt)[0]
    assert_valid(sol, reqs, opt)
    assert sol.slots[10].card.id == lock_card.id
    assert banned not in {a.card.id for a in sol.slots}


def test_alternatives_are_distinct_and_sorted(uni):
    sols = solve(uni, [R(ReqType.TEAM_RATING, 83)], SolveOptions(alternatives=2))
    assert len(sols) == 3
    sets = [frozenset(a.card.id for a in s.slots) for s in sols]
    assert len(set(sets)) == 3
    assert [s.total_cost for s in sols] == sorted(s.total_cost for s in sols)


def test_random_requirements_always_valid(uni):
    rng = random.Random(3)
    for _ in range(12):
        reqs = [R(ReqType.TEAM_RATING, rng.randint(75, 85))]
        if rng.random() < 0.6:
            reqs.append(R(ReqType.TEAM_CHEM, rng.randint(5, 30)))
        if rng.random() < 0.5:
            reqs.append(R(ReqType.COUNT, rng.randint(1, 4), Op.MIN, "league", (rng.randrange(12),)))
        if rng.random() < 0.4:
            reqs.append(R(ReqType.DISTINCT, rng.randint(2, 5), Op.MAX, "nation"))
        sol = solve(uni, reqs, SolveOptions(time_limit_s=8))[0]
        if sol.status in ("OPTIMAL", "FEASIBLE"):
            assert_valid(sol, reqs)


def test_index_is_consistent(uni):
    ix = CardIndex.build(uni)
    assert all(uni[ix.by_id[c.id]] is c for c in uni[:500])
    assert sum(len(v) for v in ix.by_league.values()) == len(uni)
    assert all(uni[i].rating == 84 for i in ix.by_rating[84])
