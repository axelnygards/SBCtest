"""Squad solving for the API: solver input, result labelling and the shared cache.

Database work runs in the thread pool so the event loop stays free while a solve waits for
a worker process.
"""
import asyncio
import logging
import time
from datetime import datetime, timezone

from fastapi import HTTPException
from starlette.concurrency import run_in_threadpool

from . import services
from .catalogue import catalogue
from .config import settings
from .db import SessionLocal
from .models import User, utcnow
from .sbc.presets import PRESETS
from .schemas import RequirementIn, SlotOut, SolutionOut, SolveIn
from .solve_cache import cache, key_for, still_valid
from .solver import runner
from .solver.evaluate import requirement_status
from .solver.formations import FORMATIONS
from .solver.types import Requirement, Solution, SolveOptions

log = logging.getLogger(__name__)
BUSY = "Många löser SBC:er just nu. Försök igen om en liten stund."


def _age_min(p, now: datetime) -> int | None:
    return int((now - p.observed_at).total_seconds() // 60) if p and p.observed_at else None


def solution_out(s: Solution, inp: services.SolveInput, opt: SolveOptions,
                 reqs: list[Requirement], formation: str) -> SolutionOut:
    now = utcnow()
    slots, est_coins, own_coins = [], 0, 0
    for a in s.slots:
        p = inp.price(a.card.id)
        if not a.card.owned and p:
            est_coins += (a.card.price or 0) if p.source in ("estimate", "default") else 0
            own_coins += (a.card.price or 0) if p.source == "own" else 0
        row = inp.row(a.card.id)
        view = services.card_view(row) if row else {}
        view.pop("definition_id", None)
        slots.append(SlotOut(
            **view, slot=a.slot, position=a.position, card_id=a.card.id,
            definition_id=row.definition_id if row else None,
            name=a.card.name, rating=a.card.rating, in_position=a.in_position,
            chemistry=a.chemistry, owned=a.card.owned, untradeable=a.card.untradeable,
            price=a.card.price, price_source=p.source if p else None,
            price_age_min=_age_min(p, now)))
    share = (lambda x: round(x / s.total_cost, 3) if s.total_cost else 0.0)
    return SolutionOut(
        status=s.status, message=s.message, total_cost=s.total_cost,
        team_rating=s.team_rating, team_chem=s.team_chem, slots=slots,
        violations=s.violations, pool_size=s.pool_size, wall_time_s=s.wall_time_s,
        estimated_cost_share=share(est_coins), own_cost_share=share(own_coins),
        owned_value=sum(int((a.card.price or 0) * opt.owned_cost_factor) for a in s.slots
                        if a.card.owned and not a.card.untradeable),
        requirements=[{"ok": ok, "actual": v} for ok, v in requirement_status(
            FORMATIONS[formation], [a.card for a in s.slots], reqs, settings.ruleset)]
        if s.slots else [])


def _options(body: SolveIn, use_club: bool) -> SolveOptions:
    return SolveOptions(formation=body.formation, ruleset=settings.ruleset,
                        use_owned=use_club, only_owned=body.only_club,
                        owned_cost_factor=body.owned_cost_factor,
                        untradeable_bonus=body.untradeable_bonus, time_limit_s=body.time_limit_s,
                        alternatives=body.alternatives, excluded_ids=frozenset(body.excluded_ids),
                        locked=body.locked)


async def _compute(db, body: SolveIn, user: User | None, use_club: bool, platform: str
                   ) -> tuple[list[SolutionOut], int]:
    overrides = body.prices.to_domain() if body.prices else None
    inp = await run_in_threadpool(services.cards_for_solve, db, user if use_club else None,
                                  platform, body.buy_from_market, overrides)
    opt = _options(body, use_club)
    reqs = [r.to_domain() for r in body.requirements]
    try:
        sols = await runner.solve_guarded(inp.cards, reqs, opt, settings.solver_queue)
    except runner.SolverBusy:
        raise HTTPException(503, BUSY)
    return [solution_out(s, inp, opt, reqs, body.formation) for s in sols], inp.cat.version


def _cacheable(body: SolveIn, use_club: bool) -> bool:
    """Market-only requests without anything personal give the same answer for everyone."""
    return (not use_club and body.buy_from_market and not body.only_club and not body.locked
            and not body.excluded_ids and not (body.prices and (body.prices.ratings
                                                                 or body.prices.cards)))


def _lookup(db, key: str, platform: str, time_limit_s: float, max_age_s: float):
    entry = cache.get(key)
    if entry is None or (entry["time_limit_s"] < time_limit_s and not entry["optimal"]):
        return None
    cat = catalogue(db, platform)
    now = {int(d): (cat.prices[int(d)].price if int(d) in cat.prices and cat.in_market(int(d))
                    else None) for d in entry["buys"]}
    if not still_valid(entry, cat.version, now, max_age_s):
        return None
    age = int(time.time() - entry["at"])
    return [SolutionOut(**s, cached_age_s=age) for s in entry["solutions"]]


async def solve_squads(db, body: SolveIn, user: User | None, platform: str | None = None,
                       max_age_s: float | None = None) -> list[SolutionOut]:
    if body.formation not in FORMATIONS:
        raise HTTPException(422, f"Okänd formation {body.formation}")
    platform = platform or (user.platform if user else "console")
    use_club = body.use_club and user is not None
    if not _cacheable(body, use_club):
        return (await _compute(db, body, user, use_club, platform))[0]

    key = key_for(platform, body.formation, [r.model_dump(mode="json") for r in body.requirements],
                  body.alternatives)
    max_age = settings.solve_cache_ttl_s if max_age_s is None else max_age_s
    hit = await run_in_threadpool(_lookup, db, key, platform, body.time_limit_s, max_age)
    if hit is not None:
        return hit
    if key in cache.inflight:  # the same SBC is being solved right now: share that answer
        return await asyncio.shield(cache.inflight[key])
    fut = asyncio.get_running_loop().create_future()
    cache.inflight[key] = fut
    try:
        out, version = await _compute(db, body, user, use_club, platform)
        if all(s.status in ("OPTIMAL", "FEASIBLE", "INFEASIBLE") for s in out):
            await run_in_threadpool(cache.put, key, {
                "version": version, "at": time.time(), "time_limit_s": body.time_limit_s,
                "optimal": all(s.status in ("OPTIMAL", "INFEASIBLE") for s in out),
                "buys": {str(sl.definition_id): sl.price for s in out for sl in s.slots
                         if not sl.owned and sl.definition_id is not None},
                "solutions": [s.model_dump(exclude={"cached_age_s"}) for s in out]})
        fut.set_result(out)
        return out
    except BaseException as e:
        fut.set_exception(e if isinstance(e, Exception) else RuntimeError("avbruten"))
        fut.exception()  # mark retrieved: nobody may be waiting
        raise
    finally:
        cache.inflight.pop(key, None)


# --- background: keep the active SBC presets solved -------------------------------------------

def _active_puzzles() -> list[dict]:
    now = datetime.now(timezone.utc)
    return [p for p in PRESETS if p["kind"] == "puzzle" and not (
        p["expires"] and datetime.fromisoformat(p["expires"].replace("Z", "+00:00")) < now)]


def preset_request(p: dict) -> SolveIn:
    """What the app sends for a preset when the user buys everything on the market."""
    return SolveIn(formation=p["formation"], use_club=False, only_club=False,
                   buy_from_market=True, alternatives=0, time_limit_s=30,
                   requirements=[RequirementIn(**r) for r in p["requirements"]])


async def warm_presets() -> int:
    """Solve every active preset whose cached answer is getting old; returns solves run."""
    n = 0
    fresh_for = max(60, settings.warm_presets_min * 60 - 120)  # renew before users see it age
    for platform in settings.warm_platforms:
        for p in _active_puzzles():
            for _ in range(60):  # users first: wait (up to 5 min) while the solver is busy
                if not runner.busy():
                    break
                await asyncio.sleep(5)
            with SessionLocal() as db:
                try:
                    out = await solve_squads(db, preset_request(p), None, platform, fresh_for)
                except HTTPException:
                    continue
            n += any(s.cached_age_s is None for s in out)
    return n


async def warm_loop():
    await asyncio.sleep(30)  # let the app (and a first EA import) start
    while True:
        try:
            t0 = time.monotonic()
            n = await warm_presets()
            log.info("presets warmed: %d solved in %.0f s", n, time.monotonic() - t0)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("warming presets failed")
        await asyncio.sleep(settings.warm_presets_min * 60)

