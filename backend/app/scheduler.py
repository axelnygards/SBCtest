"""Background jobs (APScheduler): EA ratings refresh and price estimates."""
import logging
import os

from apscheduler.schedulers.background import BackgroundScheduler

from .config import settings
from .db import SessionLocal

log = logging.getLogger(__name__)


def refresh_ratings_job():
    from .datasources.ea_ratings import EaRatingsSource
    from .services import upsert_base_players, upsert_leagues
    src = EaRatingsSource(mode=settings.ea_ratings_mode)
    with SessionLocal() as db:
        upsert_leagues(db, src.leagues())
        n = upsert_base_players(db, src.players())
        db.commit()
    log.info("EA ratings refresh: %d cards changed (mode=%s, total %s)", n, src.resolved_mode, src.total)
    refresh_estimates_job()


def refresh_estimates_job():
    from .prices import refresh_estimates
    with SessionLocal() as db:
        n = refresh_estimates(db, "console") + refresh_estimates(db, "pc")
        db.commit()
    log.info("price estimates refreshed: %d changed", n)


def start_scheduler() -> BackgroundScheduler | None:
    if os.environ.get("DISABLE_SCHEDULER"):
        return None
    s = BackgroundScheduler(timezone="UTC")
    if settings.source_ea_ratings_enabled:
        from datetime import datetime, timezone

        from sqlalchemy import func, select

        from .models import Card
        with SessionLocal() as db:
            empty = not db.scalar(select(func.count(Card.definition_id)))
            # databases imported before player images were stored: refresh once now
            sample = db.scalar(select(Card).where(Card.source == "ea_ratings").limit(1))
            if sample is not None and "stats" not in (sample.names or {}):
                empty = True
        # first start: import immediately (~200 pages, a few minutes) instead of in 24 h
        # (next_run_time=None would add the job paused, so only pass it when importing now)
        first = {"next_run_time": datetime.now(timezone.utc)} if empty else {}
        s.add_job(refresh_ratings_job, "interval", hours=settings.ea_ratings_refresh_hours,
                  id="ea_ratings", max_instances=1, coalesce=True, **first)
    s.add_job(refresh_estimates_job, "interval", minutes=15, id="estimates",
              max_instances=1, coalesce=True)
    s.start()
    return s
