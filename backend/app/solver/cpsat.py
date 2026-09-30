"""CP-SAT model for cheapest SBC squad. See docs/chemistry.md and docs/rating.md."""
import os
import time
from collections import defaultdict

from ortools.sat.python import cp_model

from .evaluate import _attr_key, check, chemistry
from .formations import slots_for
from .index import CardIndex
from .pool import build_pool
from .rating import team_rating
from .rules import CHEM_RULES
from .types import (Card, CardKind, Op, ReqType, Requirement, SlotAssignment, Solution,
                    SolveOptions)

COST_SCALE = 100  # objective = cost * COST_SCALE + rating (rating is a tie-breaker)


def card_cost(c: Card, opt: SolveOptions) -> int:
    if c.owned:
        cost = 0 if c.untradeable else int((c.price or 0) * opt.owned_cost_factor)
        if c.untradeable:
            cost -= opt.untradeable_bonus
        return cost
    return c.price if c.price is not None else 10**9


def _usable(c: Card, opt: SolveOptions) -> bool:
    if c.id in opt.excluded_ids:
        return False
    if c.owned:
        return opt.use_owned
    return not opt.only_owned and c.price is not None


def _add_op(model, expr, op: Op, value: int):
    if op == Op.MIN:
        model.Add(expr >= value)
    elif op == Op.MAX:
        model.Add(expr <= value)
    else:
        model.Add(expr == value)


class _Model:
    def __init__(self, cards: list[Card], reqs: list[Requirement], opt: SolveOptions):
        self.cards, self.reqs, self.opt = cards, reqs, opt
        self.ix = CardIndex.build(cards)
        self.positions = slots_for(opt.formation)
        self.n = len(self.positions)
        self.rules = CHEM_RULES[opt.ruleset]
        self.m = cp_model.CpModel()
        self.needs_chem = any(r.type in (ReqType.TEAM_CHEM, ReqType.PLAYER_CHEM) and r.value > 0
                              for r in reqs)
        self._build()

    def _build(self):
        m, cards, n = self.m, self.cards, self.n
        P = range(len(cards))
        self.y = [m.NewBoolVar(f"y{p}") for p in P]
        m.Add(sum(self.y) == n)

        for ps in self.ix.by_base.values():  # never two versions of the same player
            if len(ps) > 1:
                m.Add(sum(self.y[p] for p in ps) <= 1)

        locked_ids = {cid: s for s, cid in self.opt.locked.items()}
        for cid in locked_ids:
            m.Add(self.y[self.ix.by_id[cid]] == 1)

        if self.needs_chem:
            self._build_slots(locked_ids)
            self._build_chem()
        for r in self.reqs:
            self._build_req(r)

        self.coefs = [card_cost(c, self.opt) * COST_SCALE + c.rating for c in cards]
        self.obj = sum(cf * y for cf, y in zip(self.coefs, self.y))
        m.Minimize(self.obj)

    # --- positions -------------------------------------------------------
    def _build_slots(self, locked_ids):
        m, cards = self.m, self.cards
        self.x = {}                                   # (p, s) -> in-position placement
        x_by_player = [[] for _ in cards]             # p -> [x vars]   (O(1) access)
        x_by_slot = [[] for _ in range(self.n)]       # s -> [x vars]
        for s, pos in enumerate(self.positions):
            for p in self.ix.by_position.get(pos, ()):  # only cards that can play here
                v = m.NewBoolVar(f"x{p}_{s}")
                self.x[p, s] = v
                x_by_player[p].append(v)
                x_by_slot[s].append(v)
        self.z = [m.NewBoolVar(f"z{p}") for p in range(len(cards))]      # placed out of position
        self.oop = [m.NewBoolVar(f"oop{s}") for s in range(self.n)]     # slot filled out of position
        for p in range(len(cards)):
            m.Add(sum(x_by_player[p]) + self.z[p] == self.y[p])
        for s in range(self.n):
            m.Add(sum(x_by_slot[s]) + self.oop[s] == 1)
        m.Add(sum(self.z) == sum(self.oop))
        for s, cid in self.opt.locked.items():
            p = self.ix.by_id[cid]
            if (p, s) in self.x:
                m.Add(self.x[p, s] == 1)
            else:
                m.Add(self.z[p] == 1)
                m.Add(self.oop[s] == 1)
        self.ipos = [sum(xs) if xs else 0 for xs in x_by_player]

    # --- chemistry -------------------------------------------------------
    def _build_chem(self):
        m, cards, R = self.m, self.cards, self.rules
        club_t, league_t, nation_t = defaultdict(list), defaultdict(list), defaultdict(list)
        icon_terms = []
        for p, c in enumerate(cards):
            ip = self.ipos[p]
            if c.kind == CardKind.ICON:
                nation_t[c.nation].append(R.icon_nation_weight * ip)
                icon_terms.append(R.icon_all_leagues * ip)
            elif c.kind == CardKind.HERO:
                nation_t[c.nation].append(R.hero_nation_weight * ip)
                league_t[c.league].append(R.hero_league_weight * ip)
            else:
                club_t[c.club].append(ip)
                league_t[c.league].append(ip)
                nation_t[c.nation].append(ip)

        def pts(name, groups, thresholds, extra=()):
            out = {}
            for g, terms in groups.items():
                count = sum(terms) + sum(extra)
                bs = []
                for k, t in enumerate(thresholds):
                    b = m.NewBoolVar(f"{name}{g}_{k}")
                    m.Add(count >= t).OnlyEnforceIf(b)
                    bs.append(b)
                m.AddImplication(bs[2], bs[1])
                m.AddImplication(bs[1], bs[0])
                out[g] = sum(bs)
            return out

        pc = pts("c", club_t, R.club)
        pl = pts("l", league_t, R.league, icon_terms)
        pn = pts("n", nation_t, R.nation)
        self.chem = []
        for p, c in enumerate(cards):
            ch = m.NewIntVar(0, 3, f"ch{p}")
            if isinstance(self.ipos[p], int):  # no valid slot in this formation
                m.Add(ch == 0)
            else:
                m.Add(ch <= 3 * self.ipos[p])
            if c.kind == CardKind.NORMAL:
                m.Add(ch <= pc[c.club] + pl[c.league] + pn[c.nation])
            self.chem.append(ch)

    # --- requirements ----------------------------------------------------
    def _build_req(self, r: Requirement):
        m, cards, y, n = self.m, self.cards, self.y, self.n
        if r.type == ReqType.TEAM_RATING:
            pass  # handled by decomposition over the rating sum, see _solve_rating()
        elif r.type == ReqType.TEAM_CHEM:
            m.Add(sum(self.chem) >= r.value)
        elif r.type == ReqType.PLAYER_CHEM:
            for p in range(len(cards)):
                m.Add(self.chem[p] >= r.value).OnlyEnforceIf(y[p])
        elif r.type == ReqType.COUNT:
            _add_op(m, sum(y[p] for p, c in enumerate(cards) if r.matches(c)), r.op, r.value)
        elif r.type in (ReqType.SAME, ReqType.DISTINCT):
            groups = defaultdict(list)
            for p, c in enumerate(cards):
                groups[_attr_key(c, r.attr)].append(y[p])
            if r.type == ReqType.SAME:
                if r.op in (Op.MIN, Op.EXACT):
                    hs = []
                    for g, ys in groups.items():
                        if len(ys) >= r.value:
                            h = m.NewBoolVar("")
                            m.Add(sum(ys) >= r.value).OnlyEnforceIf(h)
                            hs.append(h)
                    m.AddBoolOr(hs) if hs else m.Add(0 == 1)
                if r.op in (Op.MAX, Op.EXACT):
                    for ys in groups.values():
                        m.Add(sum(ys) <= r.value)
            else:
                us = []
                for ys in groups.values():
                    u = m.NewBoolVar("")
                    m.AddMaxEquality(u, ys)  # u == any selected in group
                    us.append(u)
                _add_op(m, sum(us), r.op, r.value)

    def rating_sum(self):
        return sum(c.rating * y for c, y in zip(self.cards, self.y))


def _match_positions(positions, cards):
    """Assign cards to slots maximizing in-position count (Kuhn matching)."""
    n = len(positions)
    slot_of = [-1] * n  # slot -> card idx

    def try_card(ci, seen):
        for s in range(n):
            if positions[s] in cards[ci].positions and s not in seen:
                seen.add(s)
                if slot_of[s] == -1 or try_card(slot_of[s], seen):
                    slot_of[s] = ci
                    return True
        return False

    for ci in range(len(cards)):
        try_card(ci, set())
    rest = [ci for ci in range(len(cards)) if ci not in slot_of]
    for s in range(n):
        if slot_of[s] == -1:
            slot_of[s] = rest.pop()
    return [cards[slot_of[s]] for s in range(n)]


def _extract(model: _Model, solver) -> list[Card]:
    cards, n = model.cards, model.n
    if not model.needs_chem:
        chosen = [c for p, c in enumerate(cards) if solver.Value(model.y[p])]
        locked = {s: next(c for c in chosen if c.id == cid) for s, cid in model.opt.locked.items()}
        free = [c for c in chosen if c not in locked.values()]
        free_slots = [s for s in range(n) if s not in locked]
        matched = _match_positions([model.positions[s] for s in free_slots], free)
        out = [None] * n
        for s, c in locked.items():
            out[s] = c
        for s, c in zip(free_slots, matched):
            out[s] = c
        return out
    out = [None] * n
    for (p, s), v in model.x.items():
        if solver.Value(v):
            out[s] = cards[p]
    oop_cards = [c for p, c in enumerate(cards) if solver.Value(model.z[p])]
    for s, cid in model.opt.locked.items():
        if out[s] is None:
            c = next(c for c in oop_cards if c.id == cid)
            out[s] = c
            oop_cards.remove(c)
    for s in range(n):
        if out[s] is None:
            out[s] = oop_cards.pop()
    return out


def _to_solution(model, cards_in_slots, status, t0, pool_size) -> Solution:
    opt = model.opt
    chem = chemistry(model.positions, cards_in_slots, opt.ruleset)
    return Solution(
        status=status,
        slots=[SlotAssignment(s, pos, c, pos in c.positions, ch)
               for s, (pos, c, ch) in enumerate(zip(model.positions, cards_in_slots, chem))],
        total_cost=sum(c.price or 0 for c in cards_in_slots if not c.owned),  # coins to buy
        team_rating=team_rating([c.rating for c in cards_in_slots]),
        team_chem=sum(chem),
        violations=check(model.positions, cards_in_slots, model.reqs, opt.ruleset),
        pool_size=pool_size,
        wall_time_s=round(time.monotonic() - t0, 3),
    )


# Circuit-breaker limits: callers can ask for less, never for more.
MAX_TIME_S = 30.0
MAX_POOL = 2000
MAX_ALTERNATIVES = 5
MESSAGES = {
    "INFEASIBLE": "Ingen lösning finns: kraven kan inte uppfyllas med tillgängliga spelare.",
    "UNKNOWN": "Ingen lösning hittades inom tidsgränsen.",
    "MODEL_INVALID": "Internt fel i modellen.",
}


def _new_solver(seconds: float) -> cp_model.CpSolver:
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = max(seconds, 0.01)
    solver.parameters.num_workers = min(8, os.cpu_count() or 4)
    return solver


def _excess_bound_ok(n: int, s: int, rhs: int, rmin: int, rmax: int) -> bool:
    """Can ANY n ratings in [rmin, rmax] with sum s reach the rating target?

    n*E = sum max(n*r_i - s, 0) equals the negative part, so with p players above average
    n*E <= min(p*(n*rmax - s), (n-p)*(s - n*rmin)). The bound grows with s, so once it
    fails it fails for every smaller s too.
    """
    ne = max(min(p * (n * rmax - s), (n - p) * (s - n * rmin)) for p in range(n + 1))
    return n * s + max(ne, 0) >= rhs


def _solve_rating(model: _Model, target: int, deadline: float, want: int):
    """Exact decomposition over the squad rating sum S.

    For fixed S = s the team-rating condition n*s + sum_p max(n*r_p - s, 0)*y_p >= rhs is
    linear in y, so every subproblem is a plain 0/1 model with a tight LP relaxation.
    s runs downwards from the value where no excess is needed; each subproblem only accepts
    squads cheaper than the current want-th best (cutoff) and the loop stops as soon as
    _excess_bound_ok proves no lower s can work with the cards that are still affordable.
    Returns (list of (objective, solver), proven_optimal).
    """
    n, cards = model.n, model.cards
    rhs = n * n * target - n // 2
    cap = -(-rhs // n)                    # S >= cap needs no excess at all
    ratings = [c.rating for c in cards]
    rmin, min_coef = min(ratings), min(model.coefs)
    found, proven = [], True
    for s in range(cap, n * rmin - 1, -1):
        cutoff = found[want - 1][0] if len(found) >= want else None
        if s < cap:
            affordable = [r for r, cf in zip(ratings, model.coefs)
                          if cutoff is None or cf + (n - 1) * min_coef < cutoff]
            if not affordable or not _excess_bound_ok(n, s, rhs, rmin, max(affordable)):
                break
        remaining = deadline - time.monotonic()
        if remaining <= 0.05:
            proven = False
            break
        sub = model.m.clone()
        if s == cap:
            sub.Add(model.rating_sum() >= cap)
        else:
            sub.Add(model.rating_sum() == s)
            sub.Add(sum(max(n * c.rating - s, 0) * y for c, y in zip(cards, model.y))
                    >= rhs - n * s)
        if cutoff is not None:
            sub.Add(model.obj <= cutoff - 1)
        solver = _new_solver(remaining)
        st = solver.Solve(sub)
        if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            found.append((int(solver.ObjectiveValue()), solver))
            found.sort(key=lambda f: f[0])
            del found[want:]
        if st not in (cp_model.OPTIMAL, cp_model.INFEASIBLE):
            proven = False
    return found, proven


def solve(all_cards: list[Card], reqs: list[Requirement], opt: SolveOptions | None = None,
          prune: bool = True) -> list[Solution]:
    """Return the cheapest solution (plus opt.alternatives further distinct ones).

    Always terminates: CP-SAT runs with a wall-clock deadline shared by all alternatives,
    and the pool and alternative count are clamped. On timeout or infeasibility a single
    Solution with status UNKNOWN / INFEASIBLE and a Swedish message is returned.
    """
    opt = opt or SolveOptions()
    t0 = time.monotonic()
    deadline = t0 + min(opt.time_limit_s, MAX_TIME_S)
    opt.max_pool = min(opt.max_pool, MAX_POOL)
    alternatives = min(opt.alternatives, MAX_ALTERNATIVES)

    locked_ids = set(opt.locked.values())
    usable = [c for c in all_cards if _usable(c, opt) or c.id in locked_ids]
    cards = build_pool(usable, reqs, opt, locked_ids) if prune else usable
    if len(cards) < len(slots_for(opt.formation)):
        return [Solution(status="INFEASIBLE", message=MESSAGES["INFEASIBLE"],
                         pool_size=len(cards))]
    model = _Model(cards, reqs, opt)
    rating_req = max((r.value for r in reqs if r.type == ReqType.TEAM_RATING), default=None)
    solutions = []
    if rating_req is not None:
        found, proven = _solve_rating(model, rating_req, deadline, 1 + alternatives)
        status = "OPTIMAL" if proven else "FEASIBLE"
        for _, solver in found:
            solutions.append(_to_solution(model, _extract(model, solver), status, t0, len(cards)))
        name = "INFEASIBLE" if proven else "UNKNOWN"
    else:
        name = "UNKNOWN"
        for _ in range(1 + alternatives):
            remaining = deadline - time.monotonic()
            if remaining <= 0.05:
                break
            solver = _new_solver(remaining)
            st = solver.Solve(model.m)
            name = solver.StatusName(st)
            if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
                break
            solutions.append(_to_solution(model, _extract(model, solver), name, t0, len(cards)))
            chosen = [y for y in model.y if solver.Value(y)]
            model.m.Add(sum(chosen) <= model.n - 1)  # next: a different set of cards
    if not solutions:
        solutions.append(Solution(status=name, message=MESSAGES.get(name, MESSAGES["UNKNOWN"]),
                                  pool_size=len(cards),
                                  wall_time_s=round(time.monotonic() - t0, 3)))
    return solutions
