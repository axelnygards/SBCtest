from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.datasources.base import League, NormalizedPlayer
from app.db import Base, SessionLocal, engine
from app.main import app
from app.models import PriceObservation, utcnow
from app.prices import aggregate_card, refresh_estimates
from app.services import upsert_base_players, upsert_leagues

POS = ["GK", "RB", "CB", "CB", "LB", "RM", "CM", "CM", "LM", "ST", "ST"]


def players(n=400):
    out = []
    for i in range(n):
        out.append(NormalizedPlayer(
            id=1000 + i, name=f"P{i}", rating=70 + i % 20, positions=[POS[i % 11]],
            nation_id=i % 7, nation=f"N{i % 7}", club_id=100 + i % 25, club=f"C{i % 25}",
            league_id=13 if i % 25 < 10 else 53, league="PL" if i % 25 < 10 else "LL", gender=0))
    return out


@pytest.fixture()
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        upsert_leagues(db, [League(13, "Premier League", []), League(53, "LALIGA", [])])
        upsert_base_players(db, players())
        refresh_estimates(db)
        db.commit()
    with TestClient(app) as c:
        yield c


def pair(client, platform="console"):
    r = client.post("/api/users", json={"platform": platform})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['token']}"}


def item(item_id, definition_id, rating=80, rareflag=1, pos="ST", untradeable=False, loans=0):
    return {"id": item_id, "resourceId": definition_id, "assetId": definition_id % (1 << 24),
            "rating": rating, "rareflag": rareflag, "preferredPosition": pos,
            "possiblePositions": [pos], "nation": 1, "leagueId": 13, "teamid": 100,
            "untradeable": untradeable, "loans": loans, "itemType": "player"}


def test_health_and_sync(client):
    h = client.get("/api/health").json()
    assert h["cards"] == 400 and h["version"] > 0
    s = client.get("/api/sync", params={"since": 0, "limit": 150}).json()
    assert s["hasMore"] and len(s["players"]) == 150 and s["full"]
    total, since = 0, 0
    while True:
        s = client.get("/api/sync", params={"since": since, "limit": 150}).json()
        total += len(s["players"])
        since = s["version"]
        if not s["hasMore"]:
            break
    assert total == 400
    assert client.get("/api/sync", params={"since": since}).json()["players"] == []


def test_auth_required(client):
    assert client.post("/api/ext/club", json={"items": []}).status_code == 401
    bad = {"Authorization": "Bearer nope"}
    assert client.post("/api/ext/club", json={"items": []}, headers=bad).status_code == 401


def test_club_import_and_me(client):
    h = pair(client)
    items = [item(1 + i, 1000 + i, pos=POS[i % 11]) for i in range(5)]
    items.append(item(99, 1005, loans=3))                      # loan: imported, never used
    items.append({"id": 7, "itemType": "training"})             # non-player: ignored
    r = client.post("/api/ext/club", json={"items": items}, headers=h).json()
    assert r["imported"] == 6
    me = client.get("/api/me", headers=h).json()
    assert me["club_size"] == 6 and me["club_imported_at"]
    # replace=True replaces the previous import
    client.post("/api/ext/club", json={"items": items[:2]}, headers=h)
    assert client.get("/api/me", headers=h).json()["club_size"] == 2


def test_special_card_learned_from_club(client):
    h = pair(client)
    special = (3 << 24) + 1010
    client.post("/api/ext/club", json={"items": [item(5, special, rating=88, rareflag=3)]}, headers=h)
    s = client.get("/api/sync", params={"since": 0, "limit": 20000}).json()
    row = next(p for p in s["players"] if p["id"] == str(special))
    assert row["baseId"] == 1010 and row["rarity"] == "special_3" and row["rating"] == 88


def test_observations_make_live_price(client):
    h = pair(client)
    obs = {"prices": [{"definition_id": 1012, "kind": "bin_min", "price": 1900},
                      {"definition_id": 1012, "kind": "limit_min", "price": 700}]}
    r = client.post("/api/ext/observations", json=obs, headers=h).json()
    assert r == {"accepted": 2, "prices_changed": 1}
    s = client.get("/api/sync", params={"since": 0, "limit": 20000}).json()
    p = next(p for p in s["prices"] if p["id"] == "1012")
    assert p["price"] == 1900 and p["source"] == "live"


def test_invalid_observations_rejected(client):
    h = pair(client)
    obs = {"prices": [{"definition_id": 1012, "kind": "bin_min", "price": 5}]}
    assert client.post("/api/ext/observations", json=obs, headers=h).json()["accepted"] == 0


def test_solve_uses_club_and_labels_prices(client):
    h = pair(client)
    # own an 11-man in-position squad rated 85-89 (ratings 70+i%20 -> i%20 in 15..19)
    owned = [i for i in range(400) if 15 <= i % 20 <= 19][:11]
    client.post("/api/ext/club", json={"items": [item(500 + k, 1000 + i, rating=70 + i % 20, pos=POS[i % 11])
                                                 for k, i in enumerate(owned)]}, headers=h)
    body = {"formation": "4-4-2", "requirements": [{"type": "team_rating", "value": 80}],
            "time_limit_s": 10}
    sols = client.post("/api/solve", json=body, headers=h).json()
    s = sols[0]
    assert s["status"] == "OPTIMAL" and s["team_rating"] >= 80
    bought = [x for x in s["slots"] if not x["owned"]]
    assert all(x["price_source"] in ("live", "estimate", "default") for x in bought)
    assert s["total_cost"] == sum(x["price"] for x in bought)
    # anonymous solve works too (market only)
    anon = client.post("/api/solve", json=body).json()[0]
    assert anon["status"] == "OPTIMAL" and not any(x["owned"] for x in anon["slots"])
    assert anon["total_cost"] >= s["total_cost"]


def test_solve_infeasible_message(client):
    body = {"requirements": [{"type": "team_rating", "value": 95}], "time_limit_s": 5}
    s = client.post("/api/solve", json=body).json()[0]
    assert s["status"] == "INFEASIBLE" and "Ingen lösning" in s["message"]


def test_rate_limit(client):
    from app.api import routes
    h = pair(client)
    routes.observation_limit.max_calls = 3
    try:
        codes = [client.post("/api/ext/observations", json={}, headers=h).status_code for _ in range(5)]
        assert codes[:3] == [200] * 3 and codes[3] == 429
    finally:
        routes.observation_limit.max_calls = 60


# --- price aggregation rules -------------------------------------------------------------

def O(price, reporter="a", kind="bin_min", minutes_ago=5):
    return PriceObservation(definition_id=1, platform="console", kind=kind, price=price,
                            reporter=reporter, observed_at=utcnow() - timedelta(minutes=minutes_ago))


def test_aggregate_lowest_recent_bin():
    r = aggregate_card([O(2000), O(1800, "b"), O(1500, "c", minutes_ago=200)], utcnow())
    assert r.price == 1800 and r.n_obs == 2  # last hour preferred over older data


def test_aggregate_rejects_single_troll_report():
    obs = [O(2000, "a"), O(2100, "b"), O(1900, "c"), O(300, "troll")]
    assert aggregate_card(obs, utcnow()).price == 1900
    obs.append(O(310, "second"))  # confirmed by an independent reporter -> accepted
    assert aggregate_card(obs, utcnow()).price == 300


def test_aggregate_respects_ea_limits():
    obs = [O(650, "a"), O(900, "b"), O(700, kind="limit_min")]
    r = aggregate_card(obs, utcnow())
    assert r.price == 900 and r.min_limit == 700


def test_aggregate_ignores_old():
    assert aggregate_card([O(1000, minutes_ago=60 * 24)], utcnow()) is None


def test_estimates_follow_live_prices(client):
    h = pair(client)
    # all rating-85 cards: i%20 == 15. Observe two of them live at 3000 and 3400
    r85 = [1000 + i for i in range(400) if i % 20 == 15]
    for did, p in ((r85[0], 3000), (r85[1], 3400)):
        client.post("/api/ext/observations", headers=h,
                    json={"prices": [{"definition_id": did, "kind": "bin_min", "price": p}]})
    with SessionLocal() as db:
        db.execute(delete(PriceObservation).where(PriceObservation.price < 0))
        refresh_estimates(db)
        db.commit()
    s = client.get("/api/sync", params={"since": 0, "limit": 20000}).json()
    est = next(p for p in s["prices"] if p["id"] == str(r85[2]))
    assert est["source"] == "estimate" and est["price"] == 3200  # median of 3000/3400


def test_club_listing_and_nations(client):
    h = pair(client)
    client.post("/api/ext/club", json={"items": [item(1, 1003, rating=73), item(2, 1001, rating=71)]}, headers=h)
    rows = client.get("/api/club", headers=h).json()
    assert [r["definition_id"] for r in rows] == [1003, 1001]
    assert rows[0]["price_source"] in ("estimate", "default")
    nats = client.get("/api/nations").json()
    assert {"id": 0, "name": "N0"} in nats and len(nats) == 7
