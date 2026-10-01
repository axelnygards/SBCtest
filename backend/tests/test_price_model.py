"""The price model and in-app price reports (no extension, no account)."""
from datetime import timedelta

from app.db import SessionLocal
from app.models import Price, PriceObservation, utcnow
from app.prices import PriceModel, aggregate_card, refresh_estimates

from .test_api import client, pair  # noqa: F401  (fixture)


def O(price, reporter="a", kind="bin_min", minutes_ago=5):
    return PriceObservation(definition_id=1, platform="console", kind=kind, price=price,
                            reporter=reporter, observed_at=utcnow() - timedelta(minutes=minutes_ago))


def test_model_interpolates_between_ratings_in_log_space():
    m = PriceModel({(82, "rare"): 800, (86, "rare"): 3200}, {})
    v84, src = m.estimate(84, "rare")
    assert src == "estimate" and v84 == 1600  # geometric middle
    assert m.estimate(83, "rare")[0] < v84 < m.estimate(85, "rare")[0]


def test_model_uses_other_group_and_floors_then_default():
    m = PriceModel({(84, "rare"): 1500}, {80: 600})
    assert m.estimate(84, "common") == (1300, "estimate")   # 1500 / 1.15, rounded
    assert m.estimate(80, "common") == (600, "estimate")    # users' fodder floor
    assert m.estimate(60, "rare")[1] == "default"           # nothing near: labelled default


def test_single_report_far_below_estimate_needs_a_second_reporter():
    assert aggregate_card([O(300, "troll", "report")], utcnow(), reference=2000) is None
    two = [O(300, "a", "report"), O(310, "b", "report")]
    assert aggregate_card(two, utcnow(), reference=2000).price == 300
    assert aggregate_card([O(1700, "a", "report")], utcnow(), reference=2000).price == 1700


def test_sold_price_counts_as_market_price():
    assert aggregate_card([O(900, kind="sold")], utcnow()).price == 900


def test_report_without_account_makes_live_price(client):
    r = client.post("/api/prices/report", json={"cards": {"1012": 1800}}).json()
    assert r["accepted"] == 1 and r["prices_changed"] == 1
    with SessionLocal() as db:
        p = db.get(Price, (1012, "console"))
        assert p.source == "live" and p.price == 1800


def test_extension_cannot_send_reports_and_reports_cannot_set_limits(client):
    h = pair(client)
    r = client.post("/api/ext/observations", headers=h, json={"prices": [
        {"definition_id": 1012, "kind": "sold", "price": 1600}]}).json()
    assert r["accepted"] == 1
    bad = client.post("/api/ext/observations", headers=h, json={"prices": [
        {"definition_id": 1012, "kind": "report", "price": 1600}]})
    assert bad.status_code == 422


def test_rating_reports_need_two_reporters_and_move_estimates(client):
    # rating 70 cards in the fixture: i % 20 == 0
    client.post("/api/prices/report", json={"ratings": {"70": 900}},
                headers={"X-Real-IP": "1.1.1.1"})
    with SessionLocal() as db:
        refresh_estimates(db)
        db.commit()
    before = client.get("/api/prices/ratings").json()
    assert next(r for r in before if r["rating"] == 70)["price"] != 900
    client.post("/api/prices/report", json={"ratings": {"70": 900}},
                headers={"X-Real-IP": "2.2.2.2"})
    with SessionLocal() as db:
        refresh_estimates(db)
        db.commit()
    after = client.get("/api/prices/ratings").json()
    assert next(r for r in after if r["rating"] == 70) == {"rating": 70, "price": 900, "source": "estimate"}
    st = client.get("/api/prices/status").json()
    assert st["rating_floors"] == {"70": 900}


def test_card_keeps_its_own_recent_price_after_live_expires(client):
    with SessionLocal() as db:
        db.add(PriceObservation(definition_id=1012, platform="console", kind="bin_min", price=4000,
                                reporter="x", observed_at=utcnow() - timedelta(hours=20)))
        db.add(PriceObservation(definition_id=1012, platform="console", kind="bin_min", price=4400,
                                reporter="y", observed_at=utcnow() - timedelta(hours=30)))
        db.commit()
        refresh_estimates(db)
        db.commit()
        p = db.get(Price, (1012, "console"))
        assert (p.price, p.source) == (4200, "estimate")


def test_anonymous_platform_choice(client):
    client.post("/api/prices/report", json={"platform": "pc", "cards": {"1012": 5000}})
    body = {"formation": "4-4-2", "requirements": [{"type": "team_rating", "value": 70}],
            "time_limit_s": 5, "platform": "pc", "prices": {"cards": {}}}
    assert client.post("/api/solve", json=body).status_code == 200
    st = client.get("/api/prices/status", params={"platform": "pc"}).json()
    assert st["observations_24h"] == 1 and st["live_cards"] == 1
