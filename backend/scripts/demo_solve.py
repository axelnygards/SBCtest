"""Solve a few SBCs on the real FC 27 player list.

Prices are PLACEHOLDERS (a rating-based estimate) until the extension delivers real market
prices, so the coin totals are illustrative only. Rarity is unknown in the EA ratings data,
so every card is treated as common here.

    python scripts/demo_solve.py ../data/players_fc27.jsonl
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.solver.cpsat import solve  # noqa: E402
from app.solver.types import Card, Op, ReqType, Requirement as R, SolveOptions  # noqa: E402


def placeholder_price(rating: int) -> int:
    if rating < 75:
        return 300
    if rating < 82:
        return 500
    return int(700 * 1.6 ** (rating - 82)) // 50 * 50


def load(path):
    cards = []
    for line in open(path):
        p = json.loads(line)
        cards.append(Card(str(p["id"]), p["id"], p["name"], p["rating"], tuple(p["positions"]),
                          p["nation_id"], p["league_id"], p["club_id"],
                          price=placeholder_price(p["rating"])))
    return cards


SBCS = {
    "84-rated squad": [R(ReqType.TEAM_RATING, 84)],
    "86-rated squad": [R(ReqType.TEAM_RATING, 86)],
    "Premier League (min 3), rating 80, chem 20": [
        R(ReqType.TEAM_RATING, 80), R(ReqType.TEAM_CHEM, 20),
        R(ReqType.COUNT, 3, Op.MIN, "league", (13,))],
}

if __name__ == "__main__":
    cards = load(sys.argv[1] if len(sys.argv) > 1 else "../data/players_fc27.jsonl")
    print(f"{len(cards)} FC 27 base cards loaded")
    for name, reqs in SBCS.items():
        sol = solve(cards, reqs, SolveOptions(time_limit_s=20))[0]
        print(f"\n== {name}: {sol.status} {sol.message} | rating {sol.team_rating} "
              f"chem {sol.team_chem} | {sol.total_cost:,} coins (placeholder) | {sol.wall_time_s}s")
        for a in sol.slots:
            flag = "" if a.in_position else " (out of position)"
            print(f"  {a.position:4} {a.card.rating} {a.card.name:28} chem {a.chemistry}{flag}")
