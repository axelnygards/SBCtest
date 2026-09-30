"""EA ratings database (base cards). See docs/datasources.md.

Two public, unauthenticated read paths serve the same records:
  api   https://drop-api.ea.com/rating/ea-sports-fc?limit=100&offset=N&locale=en   (~40 KB/page)
  site  https://www.ea.com/_next/data/<buildId>/games/ea-sports-fc/ratings.json?page=N
        (the JSON behind EA's own ratings page, ~1 MB/page)
At the start of a season EA's page switches to the new game before the API does (seen
2026-09-30: page = FC 27 with 19,789 players, API still FC 26 with 17,873). `auto` compares
the first page of both and uses the API only when it serves the same data as the page.
Requests are sequential and rate limited (default 1 s apart); no protection is bypassed.
"""
import argparse
import json
import logging
import re
import time
import zlib
from typing import Iterator

import httpx

from .base import League, NormalizedPlayer

log = logging.getLogger(__name__)

API_URL = "https://drop-api.ea.com/rating/ea-sports-fc"
SITE_URL = "https://www.ea.com/games/ea-sports-fc/ratings"
NEXT_DATA_URL = "https://www.ea.com/_next/data/{build}/games/ea-sports-fc/ratings.json"
PAGE_SIZE = 100
UA = "fut-sbc-solver/0.1 (personal SBC helper; contact via GitHub)"
_NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)


def pseudo_league_id(name: str) -> int:
    """Stable negative id for a league we only know by name."""
    return -(zlib.crc32(name.encode()) & 0x7FFFFFFF)


class EaRatingsSource:
    name = "ea_ratings"

    def __init__(self, mode: str = "auto", delay_s: float = 1.0, client: httpx.Client | None = None,
                 enabled: bool = True):
        assert mode in ("auto", "api", "site")
        self.mode, self.delay_s, self.enabled = mode, delay_s, enabled
        self.client = client or httpx.Client(timeout=30, headers={"User-Agent": UA},
                                             follow_redirects=True)
        self._build: str | None = None
        self._site_first: dict | None = None  # pageProps of page 1
        self._league_of_club: dict[int, int] = {}
        self._leagues: list[League] | None = None
        self._last = 0.0
        self.total: int | None = None
        self.resolved_mode: str | None = None

    # --- http ----------------------------------------------------------------------
    def _get(self, url: str, **params) -> httpx.Response:
        wait = self._last + self.delay_s - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        for attempt in range(4):
            r = self.client.get(url, params=params or None)
            self._last = time.monotonic()
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(2 ** attempt * max(self.delay_s, 0.5))
                continue
            return r
        return r

    # --- site ----------------------------------------------------------------------
    def _load_site(self):
        r = self._get(SITE_URL)
        r.raise_for_status()
        m = _NEXT_DATA_RE.search(r.text)
        if not m:
            raise RuntimeError("EA ratings page: __NEXT_DATA__ not found (page layout changed?)")
        data = json.loads(m.group(1))
        self._build = data["buildId"]
        self._site_first = data["props"]["pageProps"]

    def _site_page(self, page: int) -> dict:
        if page == 1 and self._site_first is not None:
            return self._site_first
        for _ in range(2):
            r = self._get(NEXT_DATA_URL.format(build=self._build), page=page)
            if r.status_code == 404:  # EA deployed a new build: refresh buildId once
                self._load_site()
                continue
            r.raise_for_status()
            return r.json()["pageProps"]
        raise RuntimeError(f"EA ratings page {page}: build id keeps changing")

    # --- api -----------------------------------------------------------------------
    def _api_page(self, offset: int) -> dict:
        r = self._get(API_URL, limit=PAGE_SIZE, offset=offset, locale="en")
        r.raise_for_status()
        return r.json()

    # --- public --------------------------------------------------------------------
    def resolve_mode(self) -> str:
        if self.resolved_mode:
            return self.resolved_mode
        mode = self.mode
        if mode in ("auto", "site"):
            self._load_site()
        if mode == "auto":
            site_top = [(p["id"], p["overallRating"]) for p in
                        self._site_first["ratingDetails"]["items"][:PAGE_SIZE]]
            api = self._api_page(0)
            api_top = [(p["id"], p["overallRating"]) for p in api["items"][:PAGE_SIZE]]
            same = (api_top == site_top
                    and api.get("totalItems") == self._site_first["ratingDetails"]["totalItems"])
            mode = "api" if same else "site"
            log.info("EA ratings: api %s site -> using %s", "==" if same else "!=", mode)
        self.resolved_mode = mode
        return mode

    def leagues(self) -> list[League]:
        if self._leagues is None:
            if self._site_first is None:
                self._load_site()
            groups = self._site_first.get("ratingsFilters", {}).get("teamGroups", [])
            if not groups:  # fall back to the API filters endpoint
                groups = self._get(f"{API_URL}/filters", locale="en").json().get("teamGroups", [])
            self._leagues = []
            for g in groups:
                try:
                    lid = int(g["id"])
                except (TypeError, ValueError):
                    lid = pseudo_league_id(g.get("label", ""))
                clubs = [int(t["id"]) for t in g.get("teams", [])]
                self._leagues.append(League(lid, g.get("label", ""), clubs))
                for c in clubs:
                    self._league_of_club.setdefault(c, lid)
        return self._leagues

    def normalize(self, it: dict) -> NormalizedPlayer:
        if not self._league_of_club:
            self.leagues()
        team = it.get("team") or {}
        nat = it.get("nationality") or {}
        pos = [(it.get("position") or {}).get("shortLabel")]
        pos += [a.get("shortLabel") for a in it.get("alternatePositions") or []]
        club_id = int(team.get("id") or 0)
        league_name = it.get("leagueName") or ""
        name = it.get("commonName") or " ".join(
            x for x in (it.get("firstName"), it.get("lastName")) if x)
        return NormalizedPlayer(
            id=int(it["id"]), name=name, rating=int(it["overallRating"]),
            positions=[p for p in pos if p],
            nation_id=int(nat.get("id") or 0), nation=nat.get("label", ""),
            club_id=club_id, club=team.get("label", ""),
            league_id=self._league_of_club.get(club_id, pseudo_league_id(league_name)),
            league=league_name, gender=int((it.get("gender") or {}).get("id") or 0), raw=it,
        )

    def players(self, max_pages: int | None = None) -> Iterator[NormalizedPlayer]:
        mode = self.resolve_mode()
        self.leagues()
        page, seen = 0, set()
        while max_pages is None or page < max_pages:
            if mode == "site":
                rd = self._site_page(page + 1)["ratingDetails"]
                items, self.total = rd["items"], rd["totalItems"]
            else:
                d = self._api_page(page * PAGE_SIZE)
                items, self.total = d["items"], d["totalItems"]
            if not items:
                break
            for it in items:
                if it["id"] in seen:
                    continue
                seen.add(it["id"])
                yield self.normalize(it)
            page += 1
            if page * PAGE_SIZE >= self.total:
                break


def main():
    ap = argparse.ArgumentParser(description="Download EA base ratings to JSON lines")
    ap.add_argument("--mode", default="auto", choices=["auto", "api", "site"])
    ap.add_argument("--pages", type=int, default=None)
    ap.add_argument("--delay", type=float, default=1.0)
    ap.add_argument("--out", default="players.jsonl")
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO)
    src = EaRatingsSource(a.mode, a.delay)
    n = 0
    with open(a.out, "w") as f:
        for p in src.players(a.pages):
            d = p.__dict__.copy()
            d.pop("raw")
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
            n += 1
            if n % 1000 == 0:
                log.info("%d / %s players", n, src.total)
    log.info("done: %d players (mode=%s, total reported %s)", n, src.resolved_mode, src.total)


if __name__ == "__main__":
    main()
