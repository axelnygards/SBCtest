"""Own prices, the in-memory catalogue and the shared cache for market-only solutions."""
import asyncio

import pytest

from app import solve_service
from app.solve_cache import cache, key_for
from app.solver import runner

from .test_api import client, pair  # noqa: F401  (fixture)

R80 = {"formation": "4-4-2", "requirements": [{"type": "team_rating", "value": 80}],
       "time_limit_s": 10}


def solve(client, body=R80, **kw):
    r = client.post("/api/solve", json=body, **kw)
    assert r.status_code == 200, r.text
    return r.json()[0]


def test_market_only_solution_is_cached(client):
    first = solve(client)
    assert first["status"] == "OPTIMAL" and first["cached_age_s"] is None
    again = solve(client, {**R80, "requirements": [{"type": "team_rating", "value": 80,
                                                    "label": "another label"}]})
    assert again["cached_age_s"] is not None and again["total_cost"] == first["total_cost"]
    assert [s["card_id"] for s in again["slots"]] == [s["card_id"] for s in first["slots"]]


def test_cache_skipped_for_personal_requests(client):
    solve(client)
    excl = solve(client, {**R80, "excluded_ids": [solve(client)["slots"][0]["card_id"]]})
    assert excl["cached_age_s"] is None
    own = solve(client, {**R80, "prices": {"ratings": {80: 100}}})
    assert own["cached_age_s"] is None


def test_cache_invalid_when_a_bought_card_changes_price(client):
    first = solve(client)
    did = first["slots"][0]["definition_id"]
    h = pair(client)
    client.post("/api/ext/observations", headers=h, json={"prices": [
        {"definition_id": did, "kind": "bin_min", "price": first["slots"][0]["price"] * 20}]})
    again = solve(client)
    assert again["cached_age_s"] is None
    assert did not in [s["definition_id"] for s in again["slots"]]


def test_rating_price_replaces_estimates_not_live(client):
    h = pair(client)
    r80 = [1000 + i for i in range(400) if i % 20 == 10]  # rating 80 in the fixture
    client.post("/api/ext/observations", headers=h, json={"prices": [
        {"definition_id": r80[0], "kind": "bin_min", "price": 5000}]})
    base = solve(client)
    cheap = solve(client, {**R80, "prices": {"ratings": {"80": 160}}})
    assert cheap["total_cost"] < base["total_cost"]
    for s in cheap["slots"]:
        if s["rating"] == 80:
            assert s["definition_id"] != r80[0]  # its live 5000 is kept, so it is not chosen
            assert s["price"] == 160 and s["price_source"] == "own"
    assert cheap["own_cost_share"] > 0


def test_card_price_overrides_any_price(client):
    base = solve(client)
    slot = base["slots"][3]
    pricier = solve(client, {**R80, "prices": {"cards": {str(slot["definition_id"]): 10**6}}})
    assert slot["definition_id"] not in [s["definition_id"] for s in pricier["slots"]]


def test_invalid_own_price_rejected(client):
    r = client.post("/api/solve", json={**R80, "prices": {"ratings": {"80": -5}}})
    assert r.status_code == 422


def test_rating_prices_endpoint(client):
    rows = client.get("/api/prices/ratings").json()
    assert [r["rating"] for r in rows] == list(range(70, 90))
    assert all(r["price"] > 0 and r["source"] in ("estimate", "default", "live") for r in rows)


def test_streamlined_own_prices_and_exclusions(client):
    base = client.post("/api/solve/streamlined", json={"target": 2500}).json()
    rating = base["buy"][0]["rating"]
    own = client.post("/api/solve/streamlined",
                      json={"target": 2500, "prices": {"ratings": {str(rating): 155}}}).json()
    assert own["total_coins"] < base["total_coins"] and own["own_cost_share"] > 0
    excl = client.post("/api/solve/streamlined", json={
        "target": 2500, "excluded_ids": [b["card_id"] for b in base["buy"]]}).json()
    assert {b["card_id"] for b in excl["buy"]}.isdisjoint({b["card_id"] for b in base["buy"]})


def test_busy_solver_gives_503(client, monkeypatch):
    async def busy(*a, **kw):
        raise runner.SolverBusy()
    monkeypatch.setattr(runner, "solve_guarded", busy)
    r = client.post("/api/solve", json=R80)
    assert r.status_code == 503 and "Försök igen" in r.json()["detail"]


def test_solve_rate_limit(client):
    from app.api import routes
    routes.solve_limit.max_calls = 2
    try:
        codes = [client.post("/api/solve", json=R80).status_code for _ in range(3)]
        assert codes == [200, 200, 429]
    finally:
        routes.solve_limit.max_calls = 20


def test_identical_requests_share_one_solve(client, monkeypatch):
    calls = []
    real = runner.solve_guarded

    async def slow(*a, **kw):
        calls.append(1)
        await asyncio.sleep(0.3)
        return await real(*a, **kw)
    monkeypatch.setattr(runner, "solve_guarded", slow)
    from app.db import SessionLocal
    from app.schemas import SolveIn

    async def both():
        with SessionLocal() as d1, SessionLocal() as d2:
            return await asyncio.gather(solve_service.solve_squads(d1, SolveIn(**R80), None),
                                        solve_service.solve_squads(d2, SolveIn(**R80), None))
    a, b = asyncio.run(both())
    assert len(calls) == 1 and a[0].total_cost == b[0].total_cost


def test_warm_presets_fills_cache(client, monkeypatch):
    monkeypatch.setattr(solve_service.settings, "warm_platforms", ["console"])
    # one cheap preset is enough to exercise the path
    monkeypatch.setattr(solve_service, "_active_puzzles", lambda: [
        {"formation": "4-4-2", "requirements": [{"type": "team_rating", "value": 78}]}])
    assert asyncio.run(solve_service.warm_presets()) == 1
    key = key_for("console", "4-4-2", [{"type": "team_rating", "value": 78, "op": "min",
                                        "attr": None, "values": []}], 0)
    assert cache.get(key) is not None
    assert asyncio.run(solve_service.warm_presets()) == 0  # still valid: nothing solved
    body = {"formation": "4-4-2", "requirements": [{"type": "team_rating", "value": 78}],
            "time_limit_s": 30}
    assert solve(client, body)["cached_age_s"] is not None


@pytest.mark.parametrize("expires,active", [(None, True), ("2000-01-01T00:00:00Z", False),
                                            ("2999-01-01T00:00:00Z", True)])
def test_active_puzzles_skip_expired(monkeypatch, expires, active):
    monkeypatch.setattr(solve_service, "PRESETS", [
        {"kind": "puzzle", "expires": expires}, {"kind": "streamlined", "expires": None}])
    assert len(solve_service._active_puzzles()) == int(active)
