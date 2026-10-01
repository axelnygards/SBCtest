"""Crowdsourced prices.

Every price comes from what users themselves see; nothing searches the market:
  * extension: listings in the user's own transfer-market searches and watch list, the price
    of cards the user buys or sells (real trades), EA's price limits when listing
  * app: "what does this card cost in the game?" reports and the user's own fodder price per
    rating, shared anonymously

Live price per card = the lowest credible price seen recently:
  * values outside EA's own price limits for the card are discarded
  * a value below 60 % of the recent median, or below 40 % of the current estimate, needs two
    different reporters before it counts (one troll cannot make a card look cheap)
Cards without a recent live price get an estimate, best source first:
  1. the card's own market prices from the last 72 hours (median)
  2. the median live price of cards with the same rating and rarity group
  3. users' fodder price for the rating (at least two reporters)
  4. interpolation between neighbouring ratings (log scale), then the other rarity group
  5. a default curve (labelled "default")
"""
import math
import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .models import Card, Price, PriceObservation, RatingReport, utcnow
from .sync import next_version

SUSPICIOUS_RATIO = 0.6      # below this share of the recent median: needs a second reporter
REFERENCE_RATIO = 0.4       # below this share of the current estimate: same
MARKET_KINDS = ("bin_min", "sold", "report")
EXTENSION_KINDS = ("bin_min", "sold", "limit_min", "limit_max")
RECENT_DAYS = 3             # a card's own older prices beat any group estimate
RARE_PREMIUM = 1.15         # rare vs common of the same rating, when only one is known
MAX_GAP = 5                 # interpolate between ratings at most this far apart


def default_price(rating: int) -> int:
    """Last-resort curve for gold fodder when nothing has been observed (labelled 'default')."""
    if rating < 75:
        return 250
    if rating < 82:
        return 450
    return int(700 * 1.6 ** (rating - 82)) // 50 * 50


def rarity_group(rarity: str) -> str:
    return rarity if rarity in ("common", "rare") else "special" if rarity != "unknown" else "rare"


@dataclass
class LiveResult:
    price: int
    n_obs: int
    observed_at: datetime
    min_limit: int | None
    max_limit: int | None


def aggregate_card(obs: list[PriceObservation], now: datetime,
                   reference: int | None = None) -> LiveResult | None:
    limits_min = [o.price for o in obs if o.kind == "limit_min"]
    limits_max = [o.price for o in obs if o.kind == "limit_max"]
    lo = max(limits_min) if limits_min else None
    hi = min(limits_max) if limits_max else None
    window = now - timedelta(hours=settings.price_stale_window_h)
    bins = [o for o in obs if o.kind in MARKET_KINDS and o.observed_at >= window
            and (lo is None or o.price >= lo) and (hi is None or o.price <= hi)]
    if not bins:
        return None
    med = statistics.median(o.price for o in bins)

    def credible(o: PriceObservation) -> bool:
        if o.price >= SUSPICIOUS_RATIO * med and not (reference and o.price < REFERENCE_RATIO * reference):
            return True
        confirmers = {x.reporter for x in bins if x.price <= o.price * 1.05}
        return len(confirmers) >= 2  # a suspiciously low price needs two independent reporters

    accepted = [o for o in bins if credible(o)]
    if not accepted:
        return None
    # prefer the freshest window: the last hour if we have data there
    live_cut = now - timedelta(minutes=settings.price_live_window_min)
    recent = [o for o in accepted if o.observed_at >= live_cut] or accepted
    best = min(recent, key=lambda o: (o.price, -o.observed_at.timestamp()))
    return LiveResult(best.price, len(recent), max(o.observed_at for o in recent), lo, hi)


def record_observations(db: Session, reporter: str, platform: str, rows: list[dict],
                        kinds: tuple[str, ...] = EXTENSION_KINDS) -> int:
    """rows: {definition_id, kind, price, sample_size?}; returns accepted count."""
    now = utcnow()
    n = 0
    for r in rows:
        kind, price = r.get("kind"), int(r.get("price") or 0)
        if kind not in kinds or not (150 <= price <= 15_000_000):
            continue
        db.add(PriceObservation(definition_id=int(r["definition_id"]), platform=platform,
                                kind=kind, price=price, sample_size=int(r.get("sample_size", 1)),
                                reporter=reporter, observed_at=now))
        n += 1
    db.flush()
    return n


def refresh_live(db: Session, definition_ids: set[int], platform: str) -> int:
    """Recompute live prices for the given cards; returns number of prices changed."""
    now = utcnow()
    since = now - timedelta(days=2)  # limits stay valid for a while
    obs = db.scalars(select(PriceObservation).where(
        PriceObservation.definition_id.in_(definition_ids),
        PriceObservation.platform == platform,
        PriceObservation.observed_at >= since)).all()
    by_card = defaultdict(list)
    for o in obs:
        by_card[o.definition_id].append(o)
    changed = 0
    for did, card_obs in by_card.items():
        row = db.get(Price, (did, platform))
        res = aggregate_card(card_obs, now, row.price if row and row.source != "live" else None)
        if res is None:
            if row and row.source == "live" and card_obs:
                row.min_limit = max((o.price for o in card_obs if o.kind == "limit_min"),
                                    default=row.min_limit)
            continue
        if row is None:
            row = Price(definition_id=did, platform=platform)
            db.add(row)
        if (row.price, row.source) != (res.price, "live") or row.observed_at != res.observed_at:
            row.price, row.source, row.n_obs = res.price, "live", res.n_obs
            row.observed_at, row.min_limit, row.max_limit = res.observed_at, res.min_limit, res.max_limit
            row.version = next_version(db)
            changed += 1
    db.flush()
    return changed


def record_rating_reports(db: Session, reporter: str, platform: str, ratings: dict[int, int]) -> int:
    now = utcnow()
    n = 0
    for rating, price in ratings.items():
        if 45 <= int(rating) <= 99 and 150 <= int(price) <= 15_000_000:
            db.add(RatingReport(platform=platform, rating=int(rating), price=int(price),
                                reporter=reporter, observed_at=now))
            n += 1
    db.flush()
    return n


def rating_floors(db: Session, platform: str, now: datetime) -> dict[int, int]:
    """Users' fodder price per rating: median of each reporter's latest report (48 h)."""
    latest: dict[tuple[int, str], RatingReport] = {}
    for r in db.scalars(select(RatingReport).where(
            RatingReport.platform == platform,
            RatingReport.observed_at >= now - timedelta(hours=48)).order_by(RatingReport.observed_at)):
        latest[(r.rating, r.reporter)] = r
    by_rating = defaultdict(list)
    for (rating, _), r in latest.items():
        by_rating[rating].append(r.price)
    return {k: int(statistics.median(v)) for k, v in by_rating.items()
            if len(v) >= settings.rating_report_min_reporters}


def recent_card_prices(db: Session, platform: str, now: datetime) -> dict[int, tuple[int, int]]:
    """Median market price per card over the last few days and its number of reporters."""
    by_card = defaultdict(list)
    for did, price, who in db.execute(select(
            PriceObservation.definition_id, PriceObservation.price, PriceObservation.reporter).where(
            PriceObservation.platform == platform, PriceObservation.kind.in_(MARKET_KINDS),
            PriceObservation.observed_at >= now - timedelta(days=RECENT_DAYS))):
        by_card[did].append((price, who))
    return {did: (int(statistics.median(p for p, _ in v)), len({w for _, w in v}))
            for did, v in by_card.items()}


class PriceModel:
    """Typical price per (rating, rarity group) from a few anchors."""

    def __init__(self, group_median: dict[tuple[int, str], int], floors: dict[int, int]):
        self.anchors: dict[str, dict[int, int]] = defaultdict(dict)
        for (rating, g), v in group_median.items():
            self.anchors[g][rating] = v
        for rating, v in floors.items():  # fodder floor: the cheapest common/rare of that rating
            for g in ("common", "rare"):
                self.anchors[g].setdefault(rating, v)

    def _interp(self, rating: int, g: str, stage: int) -> int | None:
        """stage 0: exact rating, 1: between two ratings, 2: one side only."""
        a = self.anchors.get(g) or {}
        if stage == 0:
            return a.get(rating)
        lo = max((r for r in a if rating - MAX_GAP <= r < rating), default=None)
        hi = min((r for r in a if rating < r <= rating + MAX_GAP), default=None)
        if stage == 1:
            if lo is None or hi is None:
                return None
            t = (rating - lo) / (hi - lo)
            return int(math.exp(math.log(a[lo]) * (1 - t) + math.log(a[hi]) * t))
        near = lo if lo is not None else hi
        if near is None:
            return None
        # one side only: follow the shape of the default curve, never below the lower anchor
        v = a[near] * default_price(rating) / default_price(near)
        return int(max(v, a[near]) if near < rating else min(v, a[near]))

    def estimate(self, rating: int, g: str) -> tuple[int, str]:
        other = {"common": "rare", "rare": "common"}.get(g)
        scale = RARE_PREMIUM if g == "rare" else 1 / RARE_PREMIUM
        v = None
        for stage in (0, 1, 2):  # closer evidence first, own group before the other group
            v = self._interp(rating, g, stage)
            if v is None and other:
                o = self._interp(rating, other, stage)
                v = int(o * scale) if o is not None else None
            if v is not None:
                break
        if v is None:
            return default_price(rating), "default"
        return max(150, v // 50 * 50 if v >= 1000 else v // 10 * 10), "estimate"


def refresh_estimates(db: Session, platform: str = "console") -> int:
    """Estimate every card without a fresh live price (see the module docstring)."""
    now = utcnow()
    stale = now - timedelta(hours=settings.price_stale_window_h)
    cards = {c.definition_id: c for c in db.scalars(select(Card))}
    prices = {p.definition_id: p for p in db.scalars(select(Price).where(Price.platform == platform))}
    live_by_group = defaultdict(list)
    for did, p in prices.items():
        c = cards.get(did)
        if c and p.source == "live" and p.observed_at and p.observed_at >= stale:
            live_by_group[(c.rating, rarity_group(c.rarity))].append(p.price)
    model = PriceModel({k: int(statistics.median(v)) for k, v in live_by_group.items()},
                       rating_floors(db, platform, now))
    recent = recent_card_prices(db, platform, now)
    changed = 0
    for did, c in cards.items():
        p = prices.get(did)
        if p and p.source == "live" and p.observed_at and p.observed_at >= stale:
            continue
        value, source = model.estimate(c.rating, rarity_group(c.rarity))
        own, reporters = recent.get(did, (None, 0))
        if own is not None and (reporters >= 2 or own >= REFERENCE_RATIO * value):
            value, source = own, "estimate"  # the card's own recent prices beat any group guess
        if p and p.min_limit:
            value = max(value, p.min_limit)
        if p is None:
            p = Price(definition_id=did, platform=platform, n_obs=0)
            db.add(p)
        if (p.price, p.source) != (value, source):
            p.price, p.source = value, source
            p.version = next_version(db)
            changed += 1
    db.flush()
    return changed


def status(db: Session, platform: str) -> dict:
    """How good the price data is right now (shown in the app)."""
    now = utcnow()
    day = now - timedelta(hours=24)
    obs = db.execute(select(PriceObservation.reporter, PriceObservation.definition_id).where(
        PriceObservation.platform == platform, PriceObservation.kind.in_(MARKET_KINDS),
        PriceObservation.observed_at >= day)).all()
    fresh = now - timedelta(hours=settings.price_stale_window_h)
    live = db.scalars(select(Price.definition_id).where(
        Price.platform == platform, Price.source == "live", Price.observed_at >= fresh)).all()
    return {"platform": platform, "observations_24h": len(obs),
            "reporters_24h": len({r for r, _ in obs}), "cards_24h": len({d for _, d in obs}),
            "live_cards": len(live), "rating_floors": rating_floors(db, platform, now)}
