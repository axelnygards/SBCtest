"""CP-SAT model for cheapest SBC squad. See docs/chemistry.md and docs/rating.md."""
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, replace

from ortools.sat.python import cp_model

from .evaluate import _attr_key, check, chemistry
from .formations import slots_for
from .heuristics import greedy_squads
from .index import CardIndex
from .pool import build_pool, chem_pool
from .rating import team_rating
from .rules import CHEM_RULES
from .types import (Card, CardKind, Op, ReqType, Requirement, SlotAssignment, Solution,
                    SolveOptions)



def card_cost(c: Card, opt: SolveOptions) -> int:
    if c.owned:
        # untradeables can't be sold: free. Tradeables: the coins you give up by not selling.
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

        self.coefs = [card_cost(c, self.opt) for c in cards]  # rating tie-break: see _polish
        self.obj = sum(cf * y for cf, y in zip(self.coefs, self.y))
        m.Minimize(self.obj)

    # --- positions -------------------------------------------------------
    def _build_slots(self, locked_ids):
        """In-position placement per position TYPE, not per slot.

        Two CB slots are interchangeable, so x[p, "CB"] with capacity 2 removes that symmetry.
        z[p] = card placed out of position (chem 0), oop[pos] = slots of a type filled that way.
        """
        m, cards = self.m, self.cards
        self.mult = Counter(self.positions)
        self.x = {}                                   # (p, pos) -> in-position placement
        x_by_player = [[] for _ in cards]
        x_by_pos = defaultdict(list)
        for pos in self.mult:
            for p in self.ix.by_position.get(pos, ()):  # only cards that can play here
                v = m.NewBoolVar(f"x{p}_{pos}")
                self.x[p, pos] = v
                x_by_player[p].append(v)
                x_by_pos[pos].append(v)
        self.z = [m.NewBoolVar(f"z{p}") for p in range(len(cards))]
        self.oop = {pos: m.NewIntVar(0, k, f"oop{pos}") for pos, k in self.mult.items()}
        for p in range(len(cards)):
            m.Add(sum(x_by_player[p]) + self.z[p] == self.y[p])
        for pos, k in self.mult.items():
            m.Add(sum(x_by_pos[pos]) + self.oop[pos] == k)
        m.Add(sum(self.z) == sum(self.oop.values()))
        locked_oop = Counter()
        for slot, cid in self.opt.locked.items():
            p, pos = self.ix.by_id[cid], self.positions[slot]
            if (p, pos) in self.x:
                m.Add(self.x[p, pos] == 1)
            else:
                m.Add(self.z[p] == 1)
                locked_oop[pos] += 1
        for pos, k in locked_oop.items():
            m.Add(self.oop[pos] >= k)
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
    cards, n, positions = model.cards, model.n, model.positions
    chosen = [p for p in range(len(cards)) if solver.Value(model.y[p])]
    locked = {s: model.ix.by_id[cid] for s, cid in model.opt.locked.items()}
    out: list[Card | None] = [None] * n
    for s, p in locked.items():
        out[s] = cards[p]
    free = [p for p in chosen if p not in locked.values()]
    if not model.needs_chem:
        free_slots = [s for s in range(n) if out[s] is None]
        matched = _match_positions([positions[s] for s in free_slots], [cards[p] for p in free])
        for s, c in zip(free_slots, matched):
            out[s] = c
        return out
    in_pos = defaultdict(list)                     # pos type -> cards placed there
    oop_cards = []
    for p in free:
        pos = next((pos for pos in model.mult if (p, pos) in model.x
                    and solver.Value(model.x[p, pos])), None)
        (in_pos[pos] if pos else oop_cards).append(cards[p])
    for s in range(n):
        if out[s] is None and in_pos[positions[s]]:
            out[s] = in_pos[positions[s]].pop()
    for s in range(n):
        if out[s] is None:
            out[s] = oop_cards.pop()
    return out


def _to_solution(opt: SolveOptions, reqs: list[Requirement], cards_in_slots: list[Card],
                 status: str, t0: float, pool_size: int) -> Solution:
    positions = slots_for(opt.formation)
    chem = chemistry(positions, cards_in_slots, opt.ruleset)
    return Solution(
        status=status,
        slots=[SlotAssignment(s, pos, c, pos in c.positions, ch)
               for s, (pos, c, ch) in enumerate(zip(positions, cards_in_slots, chem))],
        total_cost=sum(c.price or 0 for c in cards_in_slots if not c.owned),  # coins to buy
        team_rating=team_rating([c.rating for c in cards_in_slots]),
        team_chem=sum(chem),
        violations=check(positions, cards_in_slots, reqs, opt.ruleset),
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


@dataclass
class _Found:
    obj: int                 # objective = coins (owned cards per card_cost)
    ids: frozenset[str]
    squad: list[Card]        # in slot order


def _new_solver(seconds: float) -> cp_model.CpSolver:
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = max(seconds, 0.01)
    solver.parameters.num_workers = 8
    return solver


def _found(model: _Model, solver) -> _Found:
    squad = _extract(model, solver)
    return _Found(sum(card_cost(c, model.opt) for c in squad), frozenset(c.id for c in squad), squad)


def _hint(model: _Model, sub: cp_model.CpModel, f: _Found):
    """Warm start: suggest a known squad (only the cards also present in this model)."""
    ids = f.ids
    for p, c in enumerate(model.cards):
        sub.AddHint(model.y[p], 1 if c.id in ids else 0)
    if model.needs_chem:
        for s, c in enumerate(f.squad):
            p, pos = model.ix.by_id.get(c.id), model.positions[s]
            if p is not None and (p, pos) in model.x:
                sub.AddHint(model.x[p, pos], 1)


def _forbid(model: _Model, sub: cp_model.CpModel, f: _Found):
    ys = [model.y[model.ix.by_id[i]] for i in f.ids if i in model.ix.by_id]
    if len(ys) == model.n:
        sub.Add(sum(ys) <= model.n - 1)


def _excess_bound_ok(n: int, s: int, rhs: int, rmin: int, rmax: int) -> bool:
    """Can ANY n ratings in [rmin, rmax] with sum s reach the rating target?

    n*E = sum max(n*r_i - s, 0) equals the negative part, so with p players above average
    n*E <= min(p*(n*rmax - s), (n-p)*(s - n*rmin)). The bound grows with s, so once it
    fails it fails for every smaller s too.
    """
    ne = max(min(p * (n * rmax - s), (n - p) * (s - n * rmin)) for p in range(n + 1))
    return n * s + max(ne, 0) >= rhs


def _keep_best(found: list[_Found], new: _Found, want: int):
    if all(f.ids != new.ids for f in found):
        found.append(new)
        found.sort(key=lambda f: f.obj)
        del found[want:]


def _cutoff(found: list[_Found], want: int) -> int | None:
    return found[want - 1].obj if len(found) >= want else None


def _solve_rating(model: _Model, target: int, deadline: float, want: int,
                  found: list[_Found]) -> bool:
    """Exact decomposition over the squad rating sum S (see docs/rating.md).

    For fixed S = s the team-rating condition n*s + sum_p max(n*r_p - s, 0)*y_p >= rhs is
    linear in y, so every subproblem is a plain 0/1 model with a tight LP relaxation.
    s runs downwards from the value where no excess is needed; each subproblem only accepts
    squads cheaper than the current want-th best (cutoff, seeded by the warm start) and the
    loop stops as soon as _excess_bound_ok proves no lower s can work with the cards that
    are still affordable. Updates `found` in place; returns True if the result is proven.
    """
    n, cards = model.n, model.cards
    rhs = n * n * target - n // 2
    cap = -(-rhs // n)                    # S >= cap needs no excess at all
    ratings = [c.rating for c in cards]
    rmin, min_coef = min(ratings), min(model.coefs)
    proven = True
    for s in range(cap, n * rmin - 1, -1):
        cutoff = _cutoff(found, want)
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
        for f in found:
            _forbid(model, sub, f)
        if found:
            _hint(model, sub, found[0])
        # one hard s must not starve the others: at most 40 % of what is left (>= 2 s)
        solver = _new_solver(min(remaining, max(2.0, 0.4 * remaining)))
        st = solver.Solve(sub)
        if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            _keep_best(found, _found(model, solver), want)
        if st not in (cp_model.OPTIMAL, cp_model.INFEASIBLE):
            proven = False
    return proven


def _solve_plain(model: _Model, deadline: float, want: int, found: list[_Found]) -> bool:
    """No rating requirement: one model, alternatives via no-good cuts.

    Each round asks for a squad cheaper than the current want-th best that is not already
    known. "No such squad" (INFEASIBLE) proves `found` optimal; running out of time does not.
    """
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0.05:
            return False
        sub = model.m.clone()
        cutoff = _cutoff(found, want)
        if cutoff is not None:
            sub.Add(model.obj <= cutoff - 1)
        for f in found:
            _forbid(model, sub, f)
        if found:
            _hint(model, sub, found[0])
        solver = _new_solver(remaining)
        st = solver.Solve(sub)
        if st == cp_model.INFEASIBLE:
            return True
        if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return False
        _keep_best(found, _found(model, solver), want)


def _polish(model: _Model, best: _Found, deadline: float) -> _Found:
    """Same coins, lowest total rating: spend fodder, keep the user's better cards."""
    remaining = deadline - time.monotonic()
    if remaining < 0.3:
        return best
    sub = model.m.clone()
    sub.Add(model.obj == best.obj)
    sub.Minimize(model.rating_sum())
    _hint(model, sub, best)
    solver = _new_solver(min(remaining, 2.0))
    if solver.Solve(sub) in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        f = _found(model, solver)
        if f.obj == best.obj:
            return f
    return best


class _BestValid(cp_model.CpSolverSolutionCallback):
    """Remembers the cheapest squad that meets the REAL requirements."""

    def __init__(self, model: _Model, reqs: list[Requirement]):
        super().__init__()
        self.model, self.reqs, self.best = model, reqs, None

    def on_solution_callback(self):
        squad = _extract(self.model, self)
        if check(self.model.positions, squad, self.reqs, self.model.opt.ruleset):
            return
        cost = sum(card_cost(c, self.model.opt) for c in squad)
        if self.best is None or cost < self.best.obj:
            self.best = _Found(cost, frozenset(c.id for c in squad), squad)
        self.StopSearch()  # cost is optimised afterwards by the main model with this as hint


def _chem_first(cards, reqs, opt, rating_req, deadline, found):
    """First squads for hard chemistry SBCs.

    Plain feasibility search wanders (5 leagues & 6 nations & 25 chem: nothing in 25 s).
    Maximising chemistry gives the search a direction (25 chem in ~8 s); it stops at the
    first squad meeting the real requirements, whose cost the main model then improves.
    (Mixing cost into this objective made the search lose its way again.) Rating uses the
    sufficient condition average >= target.
    """
    remaining = deadline - time.monotonic()
    need = max((r.value for r in reqs if r.type == ReqType.TEAM_CHEM), default=0)
    if remaining <= 0.2 or need == 0:
        return
    relaxed = [replace(r, value=min(r.value, 1)) if r.type == ReqType.TEAM_CHEM else r
               for r in reqs]
    model = _Model(cards, relaxed, opt)
    m, n = model.m, model.n
    if rating_req is not None:
        m.Add(model.rating_sum() >= -(-(n * n * rating_req - n // 2) // n))
    m.Maximize(sum(model.chem))
    cb = _BestValid(model, reqs)
    _new_solver(remaining).Solve(m, cb)
    if cb.best is not None:
        _keep_best(found, cb.best, 1)


def _run(cards, reqs, opt, deadline, want, found, rating_req) -> bool:
    model = _Model(cards, reqs, opt)
    if rating_req is not None:
        return _solve_rating(model, rating_req, deadline, want, found)
    return _solve_plain(model, deadline, want, found)


WARM_START_MIN_POOL = 400


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
    rating_req = max((r.value for r in reqs if r.type == ReqType.TEAM_RATING), default=None)
    want = 1 + alternatives
    found: list[_Found] = []
    # 1) warm start on a small pool of the cheapest cards: a good incumbent in a few seconds
    #    gives the full model a hint and a cost cutoff (finding solutions was the slow part)
    needs_chem = any(r.type in (ReqType.TEAM_CHEM, ReqType.PLAYER_CHEM) and r.value > 0
                     for r in reqs)
    # 0) constructive squads (milliseconds): a valid incumbent before CP-SAT even starts
    if needs_chem:
        for sq in greedy_squads(usable, reqs, opt, slots_for(opt.formation),
                                lambda c: card_cost(c, opt)):
            _keep_best(found, _Found(sum(card_cost(c, opt) for c in sq),
                                     frozenset(c.id for c in sq), sq), want)
    small = None
    if needs_chem and prune:
        # chemistry: few groups with many cheap players (see chem_pool); the full pool gets
        # those groups too, so the warm-start squad is always available to the full model
        small = chem_pool(usable, reqs, opt, slots_for(opt.formation), locked_ids)
        known = {c.id for c in cards}
        small += [c for f in found for c in f.squad if c.id not in {x.id for x in small}]
        cards = cards + [c for c in small if c.id not in known]
    elif len(cards) > WARM_START_MIN_POOL:
        small = build_pool(cards, reqs, replace(opt, max_pool=WARM_START_MIN_POOL), locked_ids,
                           scale=0.25)
    if needs_chem and not found:
        _chem_first(cards, reqs, opt, rating_req,
                        time.monotonic() + 0.4 * (deadline - time.monotonic()), found)
    if small is not None:
        budget = time.monotonic() + 0.35 * (deadline - time.monotonic())
        _run(small, reqs, opt, budget, want, found, rating_req)
    # 2) full pool, seeded with the warm-start squads
    proven = _run(cards, reqs, opt, deadline, want, found, rating_req)
    if found and not alternatives and rating_req is None:
        found[0] = _polish(_Model(cards, reqs, opt), found[0], deadline)
    status = "OPTIMAL" if proven else "FEASIBLE"
    solutions = [_to_solution(opt, reqs, f.squad, status, t0, len(cards)) for f in found]
    name = "INFEASIBLE" if proven else "UNKNOWN"
    if not solutions:
        solutions.append(Solution(status=name, message=MESSAGES.get(name, MESSAGES["UNKNOWN"]),
                                  pool_size=len(cards),
                                  wall_time_s=round(time.monotonic() - t0, 3)))
    return solutions
