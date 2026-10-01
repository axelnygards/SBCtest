"""Glue between the database, data sources and the solver."""
import hashlib
import secrets
import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field, replace

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .catalogue import Catalogue, CardRow, PriceInfo, catalogue, solver_card
from .datasources.base import League as SrcLeague, NormalizedPlayer
from .ea_items import WebAppItem, parse_item, rarity_of
from .models import Card, ClubItem, League, User, utcnow
from .solver.types import Card as SolverCard
from .sync import next_version


# --- users / pairing ---------------------------------------------------------------------

def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_user(db: Session, platform: str = "console") -> tuple[User, str]:
    token = secrets.token_urlsafe(24)
    user = User(id=str(uuid.uuid4()), token_hash=hash_token(token), platform=platform)
    db.add(user)
    db.flush()
    return user, token


def user_by_token(db: Session, token: str) -> User | None:
    return db.scalar(select(User).where(User.token_hash == hash_token(token)))


def reporter_id(user: User) -> str:
    return hashlib.sha256(("reporter:" + user.id).encode()).hexdigest()[:32]


# --- EA ratings ingest -------------------------------------------------------------------

def upsert_leagues(db: Session, leagues: Iterable[SrcLeague]) -> None:
    for lg in leagues:
        row = db.get(League, lg.id)
        if row is None:
            db.add(League(id=lg.id, name=lg.name))
        elif row.name != lg.name:
            row.name = lg.name


def upsert_base_players(db: Session, players: Iterable[NormalizedPlayer]) -> int:
    existing = {c.definition_id: c for c in db.scalars(select(Card).where(Card.source == "ea_ratings"))}
    changed = 0
    for p in players:
        names = {"nation": p.nation, "club": p.club, "league": p.league,
                 "img": {"face": p.avatar_url, "flag": p.nation_img, "badge": p.club_img},
                 "card_name": p.card_name, "stats": p.face_stats}
        values = dict(base_id=p.id, name=p.name, rating=p.rating, positions=p.positions,
                      nation_id=p.nation_id, league_id=p.league_id, club_id=p.club_id,
                      gender=p.gender, names=names)
        row = existing.get(p.id)
        if row is None:
            row = Card(definition_id=p.id, source="ea_ratings", **values)
            db.add(row)
        elif all(getattr(row, k) == v for k, v in values.items()):
            continue
        else:
            for k, v in values.items():
                setattr(row, k, v)
        row.version, row.updated_at = next_version(db), utcnow()
        changed += 1
    db.flush()
    return changed


# --- extension: club + cards seen in the Web App ------------------------------------------

def upsert_seen_card(db: Session, it: WebAppItem) -> None:
    """Learn rarity and special versions from items the user sees in the Web App."""
    rarity, kind = rarity_of(it.rareflag)
    row = db.get(Card, it.definition_id)
    if row is None:
        base = db.get(Card, it.base_id)
        row = Card(definition_id=it.definition_id, base_id=it.base_id,
                   name=base.name if base else f"#{it.definition_id}", rating=it.rating,
                   positions=it.positions, nation_id=it.nation_id, league_id=it.league_id,
                   club_id=it.club_id, gender=base.gender if base else 0,
                   names=base.names if base else {}, source="extension",
                   rareflag=it.rareflag, rarity=rarity, kind=kind)
        db.add(row)
    elif row.rareflag == it.rareflag and row.rating == it.rating:
        return
    else:
        row.rareflag, row.rarity, row.kind, row.rating = it.rareflag, rarity, kind, it.rating
        if it.positions:
            row.positions = it.positions
    row.version, row.updated_at = next_version(db), utcnow()


def import_club(db: Session, user: User, raw_items: list[dict], location: str = "club",
                replace: bool = True) -> int:
    items = [it for it in (parse_item(d) for d in raw_items) if it]
    if replace:
        db.execute(delete(ClubItem).where(ClubItem.user_id == user.id,
                                          ClubItem.location == location))
    for it in items:
        upsert_seen_card(db, it)
        db.merge(ClubItem(user_id=user.id, item_id=it.item_id, definition_id=it.definition_id,
                          untradeable=it.untradeable, loans=it.loans, location=location))
    user.club_imported_at = utcnow()
    db.flush()
    return len(items)


# --- solver input --------------------------------------------------------------------------

@dataclass
class PriceOverrides:
    """The user's own prices ("egna priser").

    ratings: coins per rating; replaces estimated (not live) prices of common and rare cards
    cards:   coins per definition id; replaces any price, also for special cards
    """
    ratings: dict[int, int] = field(default_factory=dict)
    cards: dict[int, int] = field(default_factory=dict)

    def __bool__(self) -> bool:
        return bool(self.ratings or self.cards)

    def apply(self, c: CardRow, p: PriceInfo | None) -> PriceInfo | None:
        if c.definition_id in self.cards:
            return PriceInfo(c.definition_id, self.cards[c.definition_id], "own")
        if c.rating in self.ratings and not c.is_special and (p is None or p.source != "live"):
            return PriceInfo(c.definition_id, self.ratings[c.rating], "own")
        return p


@dataclass
class SolveInput:
    """The cards one solve may use, plus lookups to label the result."""
    cards: list[SolverCard]
    cat: Catalogue
    owned: dict[str, tuple[CardRow, PriceInfo | None]] = field(default_factory=dict)
    own_prices: dict[int, PriceInfo] = field(default_factory=dict)

    def row(self, card_id: str) -> CardRow | None:
        if card_id in self.owned:
            return self.owned[card_id][0]
        return self.cat.cards.get(int(card_id.removeprefix("def:")))

    def price(self, card_id: str) -> PriceInfo | None:
        if card_id in self.owned:
            return self.owned[card_id][1]
        did = int(card_id.removeprefix("def:"))
        return self.own_prices.get(did) or self.cat.prices.get(did)


FACE_FALLBACK = ("https://ratings-images-prod.pulse.ea.com/FC25/full/player-portraits/"
                 "p{base_id}.png?padding=0.7")  # the pattern EA uses for FC 27 portraits too


def card_view(c: Card | CardRow) -> dict:
    """Display data for a card: names, images, rarity (for the pitch and card UI)."""
    names = c.names or {}
    img = names.get("img") or {}
    return {"definition_id": c.definition_id, "rarity": c.rarity, "kind": c.kind,
            "positions": list(c.positions or ()), "nation": names.get("nation"),
            "club": names.get("club"), "league": names.get("league"),
            "card_name": names.get("card_name") or c.name.split(" ")[-1],
            "stats": names.get("stats") or {},
            "face": img.get("face") or FACE_FALLBACK.format(base_id=c.base_id),
            "flag": img.get("flag") or None, "badge": img.get("badge") or None}


def _market(cat: Catalogue, ov: PriceOverrides, own_prices: dict[int, PriceInfo]) -> list[SolverCard]:
    if not ov:
        return cat.market  # shared, never mutated
    out, card_ids = [], {f"def:{d}" for d in ov.cards}
    for sc in cat.market:
        if sc.rating in ov.ratings or sc.id in card_ids:
            did = int(sc.id.removeprefix("def:"))
            base = cat.prices.get(did)
            p = ov.apply(cat.cards[did], base)
            if p is not base:
                own_prices[did] = p
                sc = replace(sc, price=p.price)
        out.append(sc)
    for did, coins in ov.cards.items():  # own price on a card we would not buy otherwise
        c = cat.cards.get(did)
        if c is not None and not cat.in_market(did):
            own_prices[did] = PriceInfo(did, coins, "own")
            out.append(solver_card(c, own_prices[did]))
    return out


def cards_for_solve(db: Session, user: User | None, platform: str = "console",
                    include_market: bool = True, overrides: PriceOverrides | None = None
                    ) -> SolveInput:
    """All cards the solver may use: the user's club plus (optionally) buyable market cards.

    Market cards come from the in-memory catalogue; only the club is read per request.
    Loan items are excluded (they cannot be submitted to SBCs).
    """
    ov = overrides or PriceOverrides()
    cat = catalogue(db, platform)
    inp = SolveInput(cards=[], cat=cat)
    if user is not None:
        items = db.scalars(select(ClubItem).where(ClubItem.user_id == user.id,
                                                  ClubItem.loans == 0)).all()
        if any(ci.definition_id not in cat.cards for ci in items):
            cat = inp.cat = catalogue(db, platform, max_age_s=0)  # cards new from an import
        for ci in items:
            c = cat.cards.get(ci.definition_id)
            if c is None:
                continue
            p = ov.apply(c, cat.prices.get(c.definition_id))
            sc = solver_card(c, p, ci.item_id, ci.untradeable)
            inp.cards.append(sc)
            inp.owned[sc.id] = (c, p)
    if include_market:
        inp.cards.extend(_market(cat, ov, inp.own_prices))
    return inp
