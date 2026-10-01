import time
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import prices as price_svc
from .. import services
from ..config import settings
from ..db import get_db
from ..ea_items import parse_item
from ..models import Card, ClubItem, League, Price, User, utcnow
from ..sbc.presets import PRESETS
from ..schemas import (ClubImportIn, ObservationsIn, SlotOut, SolutionOut, SolveIn,
                       StreamlinedCardOut, StreamlinedIn, StreamlinedOut, UserCreateIn, UserOut)
from ..solver.evaluate import requirement_status
from ..solver.formations import FORMATIONS
from ..solver.runner import solve_guarded
from ..solver.streamlined import item_score, solve_streamlined
from ..solver.types import SolveOptions
from ..sync import current_version

router = APIRouter(prefix="/api")


# --- auth (pairing token, never EA credentials) -------------------------------------------

def optional_user(authorization: str | None = Header(None), db: Session = Depends(get_db)):
    if not authorization:
        return None
    token = authorization.removeprefix("Bearer ").strip()
    user = services.user_by_token(db, token)
    if user is None:
        raise HTTPException(401, "Okänd token. Koppla tillägget på nytt från appen.")
    return user


def require_user(user: User | None = Depends(optional_user)) -> User:
    if user is None:
        raise HTTPException(401, "Token saknas.")
    return user


class RateLimiter:
    """Per-user sliding window. Protects the crowdsourced price data from floods."""

    def __init__(self, max_calls: int, per_s: float):
        self.max_calls, self.per_s = max_calls, per_s
        self.calls: dict[str, deque] = defaultdict(deque)

    def check(self, key: str):
        now, q = time.monotonic(), self.calls[key]
        while q and q[0] < now - self.per_s:
            q.popleft()
        if len(q) >= self.max_calls:
            raise HTTPException(429, "För många anrop, vänta en stund.")
        q.append(now)


observation_limit = RateLimiter(60, 60)
club_limit = RateLimiter(20, 3600)


# --- endpoints -------------------------------------------------------------------------------

@router.get("/health")
def health(db: Session = Depends(get_db)):
    return {"ok": True, "season": settings.season, "cards": db.scalar(select(func.count(Card.definition_id))),
            "version": current_version(db)}


@router.post("/users", response_model=UserOut)
def create_user(body: UserCreateIn, db: Session = Depends(get_db)):
    user, token = services.create_user(db, body.platform)
    db.commit()
    return UserOut(user_id=user.id, token=token, platform=user.platform)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(require_user), db: Session = Depends(get_db)):
    n = db.scalar(select(func.count()).select_from(ClubItem).where(ClubItem.user_id == user.id))
    return UserOut(user_id=user.id, platform=user.platform, club_size=n or 0,
                   club_imported_at=user.club_imported_at.isoformat() if user.club_imported_at else None)


@router.post("/ext/club")
def ext_club(body: ClubImportIn, user: User = Depends(require_user), db: Session = Depends(get_db)):
    club_limit.check(user.id)
    n = services.import_club(db, user, body.items, body.location, body.replace)
    db.commit()
    return {"imported": n}


@router.post("/ext/observations")
def ext_observations(body: ObservationsIn, user: User = Depends(require_user),
                     db: Session = Depends(get_db)):
    observation_limit.check(user.id)
    platform = body.platform or user.platform
    for d in body.items:
        it = parse_item(d)
        if it:
            services.upsert_seen_card(db, it)
    rows = [r.model_dump() for r in body.prices]
    accepted = price_svc.record_observations(db, services.reporter_id(user), platform, rows)
    changed = price_svc.refresh_live(db, {r["definition_id"] for r in rows}, platform) if rows else 0
    db.commit()
    return {"accepted": accepted, "prices_changed": changed}


@router.get("/leagues")
def leagues(db: Session = Depends(get_db)):
    return [{"id": lg.id, "name": lg.name} for lg in db.scalars(select(League).order_by(League.name))]


@router.get("/nations")
def nations(db: Session = Depends(get_db)):
    seen: dict[int, str] = {}
    for nid, names in db.execute(select(Card.nation_id, Card.names).where(Card.source == "ea_ratings")):
        if nid not in seen and names and names.get("nation"):
            seen[nid] = names["nation"]
    return sorted(({"id": k, "name": v} for k, v in seen.items()), key=lambda x: x["name"])


@router.get("/club")
def club(user: User = Depends(require_user), db: Session = Depends(get_db)):
    rows = db.execute(select(ClubItem, Card, Price)
                      .join(Card, Card.definition_id == ClubItem.definition_id)
                      .outerjoin(Price, (Price.definition_id == Card.definition_id)
                                 & (Price.platform == user.platform))
                      .where(ClubItem.user_id == user.id)
                      .order_by(Card.rating.desc())).all()
    return [{**services.card_view(c), "item_id": ci.item_id, "name": c.name, "rating": c.rating,
             "untradeable": ci.untradeable, "loans": ci.loans, "price": p.price if p else None,
             "price_source": p.source if p else None} for ci, c, p in rows]


@router.get("/formations")
def formations():
    return FORMATIONS


@router.get("/sync")
def sync(since: int = Query(0, ge=0), limit: int = Query(5000, ge=1, le=20000),
         platform: str = "console", db: Session = Depends(get_db)):
    """Delta sync for the frontend's IndexedDB (see frontend/src/lib/playerCache.ts)."""
    cards = db.scalars(select(Card).where(Card.version > since)
                       .order_by(Card.version).limit(limit)).all()
    price_rows = db.scalars(select(Price).where(Price.version > since, Price.platform == platform)
                            .order_by(Price.version).limit(limit)).all()
    has_more = len(cards) == limit or len(price_rows) == limit
    # when truncated, only advance to the smallest version we fully delivered
    tops = [rows[-1].version for rows in (cards, price_rows) if len(rows) == limit]
    version = min(tops) if tops else current_version(db)
    if tops:
        cards = [c for c in cards if c.version <= version]
        price_rows = [p for p in price_rows if p.version <= version]
    return {
        "version": version, "full": since == 0, "hasMore": has_more, "deleted": [],
        "players": [{"id": str(c.definition_id), "baseId": c.base_id, "name": c.name,
                     "rating": c.rating, "positions": c.positions, "nation": c.nation_id,
                     "league": c.league_id, "club": c.club_id, "rarity": c.rarity,
                     "kind": c.kind} for c in cards],
        "prices": [{"id": str(p.definition_id), "price": p.price, "source": p.source,
                    "updatedAt": int(p.observed_at.timestamp() * 1000) if p.observed_at else 0}
                   for p in price_rows],
    }


@router.post("/solve", response_model=list[SolutionOut])
async def solve(body: SolveIn, user: User | None = Depends(optional_user),
                db: Session = Depends(get_db)):
    if body.formation not in FORMATIONS:
        raise HTTPException(422, f"Okänd formation {body.formation}")
    platform = user.platform if user else "console"
    meta: dict = {}
    cards, price_of = services.cards_for_solve(
        db, user if body.use_club else None, platform, include_market=body.buy_from_market,
        meta=meta)
    opt = SolveOptions(formation=body.formation, ruleset=settings.ruleset,
                       use_owned=body.use_club, only_owned=body.only_club,
                       owned_cost_factor=body.owned_cost_factor,
                       untradeable_bonus=body.untradeable_bonus, time_limit_s=body.time_limit_s,
                       alternatives=body.alternatives, excluded_ids=frozenset(body.excluded_ids),
                       locked=body.locked)
    reqs = [r.to_domain() for r in body.requirements]
    sols = await solve_guarded(cards, reqs, opt)
    now = utcnow()
    out = []
    for s in sols:
        slots, est_coins = [], 0
        for a in s.slots:
            p = price_of.get(a.card.id)
            age = int((now - p.observed_at).total_seconds() // 60) if p and p.observed_at else None
            if not a.card.owned and p and p.source != "live":
                est_coins += a.card.price or 0
            did = a.card.id.removeprefix("def:") if a.card.id.startswith("def:") else None
            view = services.card_view(meta[a.card.id]) if a.card.id in meta else {}
            view.pop("definition_id", None)
            slots.append(SlotOut(
                **view, slot=a.slot, position=a.position, card_id=a.card.id,
                definition_id=int(did) if did else (p.definition_id if p else None),
                name=a.card.name, rating=a.card.rating, in_position=a.in_position,
                chemistry=a.chemistry, owned=a.card.owned, untradeable=a.card.untradeable,
                price=a.card.price, price_source=p.source if p else None, price_age_min=age))
        out.append(SolutionOut(
            status=s.status, message=s.message, total_cost=s.total_cost,
            team_rating=s.team_rating, team_chem=s.team_chem, slots=slots,
            violations=s.violations, pool_size=s.pool_size, wall_time_s=s.wall_time_s,
            estimated_cost_share=round(est_coins / s.total_cost, 3) if s.total_cost else 0.0,
            requirements=[{"ok": ok, "actual": v} for ok, v in requirement_status(
                FORMATIONS[body.formation], [a.card for a in s.slots], reqs, settings.ruleset)]
            if s.slots else []))
    return out


@router.get("/presets")
def presets():
    return PRESETS


def _age_min(p, now):
    return int((now - p.observed_at).total_seconds() // 60) if p and p.observed_at else None


@router.post("/solve/streamlined", response_model=StreamlinedOut)
def solve_streamlined_route(body: StreamlinedIn, user: User | None = Depends(optional_user),
                            db: Session = Depends(get_db)):
    """FC 27 Item Score SBCs: exact, milliseconds, so no worker process is needed."""
    platform = user.platform if user else "console"
    meta: dict = {}
    cards, price_of = services.cards_for_solve(
        db, user if body.use_club else None, platform, include_market=body.buy_from_market,
        meta=meta)
    sol = solve_streamlined(cards, body.target, body.min_ovr, body.already,
                            use_owned=body.use_club, buy_from_market=body.buy_from_market,
                            sell_factor=body.sell_factor)
    now = utcnow()

    def out(c, count=1):
        p = price_of.get(c.id)
        did = c.id.removeprefix("def:") if c.id.startswith("def:") else None
        view = services.card_view(meta[c.id]) if c.id in meta else {}
        view.pop("definition_id", None)
        return StreamlinedCardOut(
            **view, card_id=c.id, definition_id=int(did) if did else (p.definition_id if p else None),
            name=c.name, rating=c.rating, points=item_score(c.rating), count=count,
            owned=c.owned, untradeable=c.untradeable, price=c.price,
            price_source=p.source if p else None, price_age_min=_age_min(p, now))

    buy = [out(b.card, b.count) for b in sol.buy]
    est = sum((b.price or 0) * b.count for b in buy if b.price_source != "live")
    return StreamlinedOut(
        status=sol.status, message=sol.message, target=sol.target, points=sol.points,
        total_coins=sol.total_coins, owned_value=sol.owned_value,
        submit=[out(c) for c in sol.submit_owned], buy=buy,
        estimated_cost_share=round(est / sol.total_coins, 3) if sol.total_coins else 0.0)
