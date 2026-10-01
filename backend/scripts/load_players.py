"""Load a players.jsonl (from app.datasources.ea_ratings) into the database and price it.

    python scripts/load_players.py ../data/players_fc27.jsonl
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.datasources.base import League, NormalizedPlayer  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.prices import refresh_estimates  # noqa: E402
from app.services import upsert_base_players, upsert_leagues  # noqa: E402


def main(path: str):
    init_db()
    players = [NormalizedPlayer(**json.loads(line)) for line in open(path)]
    leagues = {}
    for p in players:
        leagues.setdefault(p.league_id, League(p.league_id, p.league, []))
    with SessionLocal() as db:
        upsert_leagues(db, leagues.values())
        n = upsert_base_players(db, players)
        e = refresh_estimates(db)
        db.commit()
    print(f"{len(players)} players read, {n} cards changed, {e} prices set")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "../data/players_fc27.jsonl")
