import json

import httpx

from app.datasources.ea_ratings import EaRatingsSource, pseudo_league_id
from app.datasources.futbin import FutbinSource


def item(i, rating=80, team=1, league="Premier League"):
    return {"id": i, "overallRating": rating, "firstName": "F", "lastName": f"L{i}",
            "commonName": None, "leagueName": league, "gender": {"id": 0},
            "nationality": {"id": 14, "label": "England"},
            "team": {"id": team, "label": f"Club{team}"},
            "position": {"shortLabel": "ST"}, "alternatePositions": [{"shortLabel": "CAM"}]}


GROUPS = [{"id": "13", "label": "Premier League", "teams": [{"id": 1}, {"id": 2}]}]


def props(items, total):
    return {"ratingDetails": {"items": items, "totalItems": total},
            "ratingsFilters": {"teamGroups": GROUPS}}


def page_html(p):
    return ('<html><script id="__NEXT_DATA__" type="application/json">'
            + json.dumps({"buildId": "B1", "props": {"pageProps": p}}) + "</script></html>")


def make(site_pages, api_items, api_total, build_changes=False):
    calls = []
    state = {"build": "B1"}

    def handler(req: httpx.Request):
        calls.append(str(req.url))
        if req.url.host == "drop-api.ea.com":
            off = int(req.url.params.get("offset", 0))
            return httpx.Response(200, json={"items": api_items[off:off + 100], "totalItems": api_total})
        if req.url.path.endswith("/ratings"):
            html = page_html(site_pages[0]).replace("B1", state["build"])
            return httpx.Response(200, text=html)
        if "/_next/data/" in req.url.path:
            if build_changes and state["build"] == "B1":
                state["build"] = "B2"
                return httpx.Response(404)
            assert f"/{state['build']}/" in req.url.path
            return httpx.Response(200, json={"pageProps": site_pages[int(req.url.params["page"]) - 1]})
        return httpx.Response(404)

    src = EaRatingsSource(delay_s=0, client=httpx.Client(transport=httpx.MockTransport(handler)))
    return src, calls


def test_auto_uses_site_when_api_is_old_season():
    new = [item(i, team=1 + i % 2) for i in range(150)]
    pages = [props(new[:100], 150), props(new[100:], 150)]
    old = [item(1000 + i) for i in range(120)]
    src, calls = make(pages, old, 120)
    players = list(src.players())
    assert src.resolved_mode == "site"
    assert [p.id for p in players] == list(range(150))
    assert all(p.league_id == 13 for p in players)
    assert players[0].positions == ["ST", "CAM"] and players[0].name == "F L0"


def test_auto_uses_api_when_it_matches_site():
    items = [item(i) for i in range(130)]
    pages = [props(items[:100], 130)]
    src, calls = make(pages, items, 130)
    players = list(src.players())
    assert src.resolved_mode == "api" and len(players) == 130
    assert not any("/_next/data/" in c for c in calls)


def test_refreshes_build_id_on_404():
    items = [item(i) for i in range(200)]
    pages = [props(items[:100], 200), props(items[100:], 200)]
    src, _ = make(pages, [], 0, build_changes=True)
    assert len(list(src.players())) == 200


def test_unknown_club_gets_stable_pseudo_league():
    src, _ = make([props([item(1, team=999, league="Mystery League")], 1)], [], 0)
    p = list(src.players())[0]
    assert p.league_id == pseudo_league_id("Mystery League") < 0


def test_futbin_disabled_yields_nothing():
    assert list(FutbinSource().players()) == []


def test_retries_dropped_connections():
    calls = {"n": 0}

    def handler(req):
        calls["n"] += 1
        if calls["n"] <= 2:
            raise httpx.RemoteProtocolError("Server disconnected", request=req)
        return httpx.Response(200, json={"items": [], "totalItems": 0})

    src = EaRatingsSource(mode="api", delay_s=0, client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert src._get("https://drop-api.ea.com/rating/ea-sports-fc").status_code == 200
    assert calls["n"] == 3
