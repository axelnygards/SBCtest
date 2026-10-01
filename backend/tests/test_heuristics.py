from app.solver.cpsat import card_cost, solve
from app.solver.evaluate import check
from app.solver.formations import slots_for
from app.solver.heuristics import greedy_squads
from app.solver.types import Op, ReqType, Requirement as R, SolveOptions

from .factory import Timer, card, universe

F = slots_for("4-4-2")


def test_greedy_squads_are_valid_and_sorted():
    uni = universe(seed=4)
    reqs = [R(ReqType.TEAM_CHEM, 30), R(ReqType.TEAM_RATING, 75)]
    opt = SolveOptions()
    squads = greedy_squads(uni, reqs, opt, F, lambda c: card_cost(c, opt))
    assert squads
    costs = [sum(c.price for c in sq) for sq in squads]
    assert costs == sorted(costs)
    for sq in squads:
        assert check(F, sq, reqs) == []


def test_greedy_respects_named_league():
    uni = universe(seed=5)
    reqs = [R(ReqType.TEAM_CHEM, 20), R(ReqType.COUNT, 5, Op.MIN, "league", (3,))]
    opt = SolveOptions()
    for sq in greedy_squads(uni, reqs, opt, F, lambda c: card_cost(c, opt)):
        assert sum(c.league == 3 for c in sq) >= 5


def test_full_chemistry_is_proven_quickly():
    uni = universe(seed=6)
    with Timer() as t:
        sol = solve(uni, [R(ReqType.TEAM_CHEM, 33)], SolveOptions(time_limit_s=20))[0]
    assert sol.status == "OPTIMAL" and sol.team_chem == 33 and sol.violations == []
    assert t.s < 20


def test_locked_out_of_position_card_with_chemistry():
    uni = universe(seed=7)
    gk = card(999_999, 80, pos=("GK",), price=5000)
    opt = SolveOptions(locked={10: gk.id}, time_limit_s=10)  # a goalkeeper up front
    sol = solve(uni + [gk], [R(ReqType.TEAM_CHEM, 20)], opt)[0]
    assert sol.slots[10].card.id == gk.id and not sol.slots[10].in_position
    assert sol.slots[10].chemistry == 0 and sol.team_chem >= 20 and sol.violations == []
