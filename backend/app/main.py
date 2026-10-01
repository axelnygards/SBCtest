import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import router
from .config import settings
from .db import init_db

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    from .scheduler import start_scheduler
    from .solve_service import warm_loop
    sched = start_scheduler()
    # keep the active SBCs solved so most visitors get an instant answer from the cache
    warm = asyncio.create_task(warm_loop()) if sched else None
    yield
    if warm:
        warm.cancel()
    if sched:
        sched.shutdown(wait=False)


app = FastAPI(title="FUT SBC Solver", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o for o in settings.cors_origins if "*" not in o],
    allow_origin_regex=r"chrome-extension://[a-z]{32}",
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(router)
