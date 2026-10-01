"""Crowdsourced prices.

Observations come only from what extension users themselves see in the Web App (their own
transfer-market searches and EA's price limits when listing). Nothing searches the market.

Live price per card = the lowest buy-now seen recently, protected against bad reports:
  * values outside EA's own price limits for the card are discarded
  * a value below 60 % of the recent median needs two different reporters before it counts
Cards without recent observations get an estimate: the median live price of cards with the
same rating and rarity group; if there is none, a default curve (clearly labelled).
"""
import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .models import Card, Price, PriceObservation, utcnow
from .sync import next_version

SUSPICIOUS_RATIO = 0.6


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


def aggregate_card(obs: list[PriceObservation], now: datetime) -> LiveResult | None:
    limits_min = [o.price for o in obs if o.kind == "limit_min"]
    limits_max = [o.price for o in obs if o.kind == "limit_max"]
    lo = max(limits_min) if limits_min else None
    hi = min(limits_max) if limits_max else None
    window = now - timedelta(hours=settings.price_stale_window_h)
    bins = [o for o in obs if o.kind == "bin_min" and o.observed_at >= window
            and (lo is None or o.price >= lo) and (hi is None or o.price <= hi)]
    if not bins:
        return None
    med = statistics.median(o.price for o in bins)

    def credible(o: PriceObservation) -> bool:
        if o.price >= SUSPICIOUS_RATIO * med:
            return True
        confirmers = {x.reporter for x in bins if x.price <= o.price * 1.05}
        return len(confirmers) >= 2  # a suspiciously low price needs two independent reporters

    accepted = [o for o in bins if credible(o)]
    # prefer the freshest window: the last hour if we have data there
    live_cut = now - timedelta(minutes=settings.price_live_window_min)
    recent = [o for o in accepted if o.observed_at >= live_cut] or accepted
    best = min(recent, key=lambda o: (o.price, -o.observed_at.timestamp()))
    return LiveResult(best.price, len(recent), max(o.observed_at for o in recent), lo, hi)


def record_observations(db: Session, reporter: str, platform: str, rows: list[dict]) -> int:
    """rows: {definition_id, kind, price, sample_size?}; returns accepted count."""
    now = utcnow()
    n = 0
    for r in rows:
        kind, price = r.get("kind"), int(r.get("price") or 0)
        if kind not in ("bin_min", "limit_min", "limit_max") or not (150 <= price <= 15_000_000):
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
        res = aggregate_card(card_obs, now)
        row = db.get(Price, (did, platform))
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


def refresh_estimates(db: Session, platform: str = "console") -> int:
    """Estimate every card without a fresh live price from live prices of similar cards."""
    now = utcnow()
    stale = now - timedelta(hours=settings.price_stale_window_h)
    cards = {c.definition_id: c for c in db.scalars(select(Card))}
    prices = {p.definition_id: p for p in db.scalars(select(Price).where(Price.platform == platform))}
    live_by_group = defaultdict(list)
    for did, p in prices.items():
        c = cards.get(did)
        if c and p.source == "live" and p.observed_at and p.observed_at >= stale:
            live_by_group[(c.rating, rarity_group(c.rarity))].append(p.price)
    group_median = {k: int(statistics.median(v)) for k, v in live_by_group.items()}
    changed = 0
    for did, c in cards.items():
        p = prices.get(did)
        if p and p.source == "live" and p.observed_at and p.observed_at >= stale:
            continue
        est = group_median.get((c.rating, rarity_group(c.rarity)))
        source = "estimate" if est is not None else "default"
        value = est if est is not None else default_price(c.rating)
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
