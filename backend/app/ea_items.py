"""Interpretation of item JSON from EA's FC Web App (as forwarded by the extension).

Field names follow the Web App's itemData objects. Values we are not sure about for FC 27
(rareflag numbers for Icons/Heroes) are constants here and are verified against captured data
(see docs/datasources.md); the raw JSON is kept so the mapping can be corrected later.
"""
from dataclasses import dataclass

BASE_ID_MOD = 1 << 24          # special versions: definitionId = base + k * 2^24 (fallback only)
RAREFLAG_COMMON = 0
RAREFLAG_RARE = 1
RAREFLAG_ICON = 12             # TODO verify for FC 27 with captured data
RAREFLAG_HERO = 72             # TODO verify for FC 27 with captured data


@dataclass
class WebAppItem:
    item_id: int
    definition_id: int
    base_id: int
    rating: int
    rareflag: int
    positions: list[str]
    nation_id: int
    league_id: int
    club_id: int
    untradeable: bool
    loans: int


def base_id_of(d: dict) -> int:
    for key in ("assetId", "resourceBaseId"):
        if d.get(key):
            return int(d[key])
    return int(d.get("resourceId") or d.get("definitionId") or 0) % BASE_ID_MOD


def rarity_of(rareflag: int | None) -> tuple[str, str]:
    """-> (rarity, kind) as used by the solver."""
    if rareflag is None:
        return "unknown", "normal"
    if rareflag == RAREFLAG_COMMON:
        return "common", "normal"
    if rareflag == RAREFLAG_RARE:
        return "rare", "normal"
    if rareflag == RAREFLAG_ICON:
        return "icon", "icon"
    if rareflag == RAREFLAG_HERO:
        return "hero", "hero"
    return f"special_{rareflag}", "normal"


def parse_item(d: dict) -> WebAppItem | None:
    """Parse one itemData object; returns None for non-player items."""
    if d.get("itemType", "player") != "player":
        return None
    definition_id = int(d.get("resourceId") or d.get("definitionId") or 0)
    if not definition_id:
        return None
    positions = list(d.get("possiblePositions") or [])
    pref = d.get("preferredPosition")
    if pref:
        positions = [pref] + [p for p in positions if p != pref]
    return WebAppItem(
        item_id=int(d.get("id") or 0),
        definition_id=definition_id,
        base_id=base_id_of(d),
        rating=int(d.get("rating") or 0),
        rareflag=int(d.get("rareflag") or 0),
        positions=positions,
        nation_id=int(d.get("nation") or 0),
        league_id=int(d.get("leagueId") or 0),
        club_id=int(d.get("teamid") or 0),
        untradeable=bool(d.get("untradeable")),
        loans=int(d.get("loans") or 0),
    )
