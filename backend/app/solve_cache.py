"""Shared cache for market-only solutions.

A squad bought entirely on the market is the same for every user, so popular SBCs only need
to be solved once. Entries live in Redis (shared by all backend processes) or, without
Redis, in process memory. An entry is served while it still holds:

  * exact:  the card/price version it was computed at is still current, or
  * recent: it is younger than the max age and every card it buys still costs the same.

Identical requests that arrive while one is being solved wait for that one (no stampede when
a new SBC drops and everyone opens it at once).
"""
import asyncio
import hashlib
import json
import logging
import threading
import time
from collections import OrderedDict

from .config import settings

log = logging.getLogger(__name__)

HARD_TTL_S = 6 * 3600  # storage expiry; validity is decided by version/prices (see above)


class _Memory:
    def __init__(self, max_items: int = 512):
        self.items: OrderedDict[str, tuple[float, str]] = OrderedDict()
        self.max_items = max_items
        self.lock = threading.Lock()

    def get(self, key: str) -> str | None:
        with self.lock:
            hit = self.items.get(key)
            if hit is None or hit[0] < time.time():
                self.items.pop(key, None)
                return None
            self.items.move_to_end(key)
            return hit[1]

    def set(self, key: str, value: str, ttl: int) -> None:
        with self.lock:
            self.items[key] = (time.time() + ttl, value)
            self.items.move_to_end(key)
            while len(self.items) > self.max_items:
                self.items.popitem(last=False)


class _Redis:
    def __init__(self, url: str):
        import redis
        self.r = redis.Redis.from_url(url, socket_timeout=0.5, socket_connect_timeout=0.5)

    def get(self, key: str) -> str | None:
        v = self.r.get(key)
        return v.decode() if v is not None else None

    def set(self, key: str, value: str, ttl: int) -> None:
        self.r.set(key, value, ex=ttl)


class SolveCache:
    def __init__(self, redis_url: str | None):
        self.memory = _Memory()
        self.redis = _Redis(redis_url) if redis_url else None
        self.inflight: dict[str, asyncio.Future] = {}

    def _call(self, op: str, *args):
        if self.redis is not None:
            try:
                return getattr(self.redis, op)(*args)
            except Exception as e:  # Redis down: keep serving from memory
                log.warning("solve cache: redis %s failed (%s), using memory", op, e)
        return getattr(self.memory, op)(*args)

    def get(self, key: str) -> dict | None:
        raw = self._call("get", key)
        return json.loads(raw) if raw else None

    def put(self, key: str, entry: dict) -> None:
        self._call("set", key, json.dumps(entry, separators=(",", ":")), HARD_TTL_S)

    def clear(self) -> None:
        self.memory = _Memory()
        self.inflight.clear()


def key_for(platform: str, formation: str, requirements: list[dict], alternatives: int) -> str:
    """Only what changes the answer: labels and time limits are left out on purpose."""
    reqs = [[r["type"], r["value"], r["op"], r.get("attr"), list(r.get("values") or [])]
            for r in requirements]
    blob = json.dumps([settings.season, settings.ruleset, platform, formation, reqs, alternatives],
                      sort_keys=True, default=str)
    return "solve:" + hashlib.sha256(blob.encode()).hexdigest()[:40]


def still_valid(entry: dict, version: int, prices: dict[int, int | None],
                max_age_s: float) -> bool:
    """prices: current price per definition id the entry buys (None = no longer buyable)."""
    if entry["version"] == version:
        return True
    if not entry["buys"] or time.time() - entry["at"] > max_age_s:
        return False  # "no solution" answers only hold while nothing at all has changed
    return all(prices.get(int(did)) == coins for did, coins in entry["buys"].items())


cache = SolveCache(settings.redis_url)
