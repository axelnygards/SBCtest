"""Glue between the database, data sources and the solver."""
import hashlib
import secrets
import uuid
from collections.abc import Iterable

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .datasources.base import League as SrcLeague, NormalizedPlayer
from .ea_items import WebAppItem, parse_item, rarity_of
from .models import Card, ClubItem, League, Price, User, utcnow
from .solver.types import Card as SolverCard, CardKind
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
        names = {"nation": p.nation, "club": p.club, "league": p.league}
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

def _solver_card(c: Card, price: Price | None, owned: ClubItem | None) -> SolverCard:
    kind = CardKind(c.kind) if c.kind in ("normal", "icon", "hero") else CardKind.NORMAL
    return SolverCard(
        id=f"item:{owned.item_id}" if owned else f"def:{c.definition_id}",
        base_id=c.base_id, name=c.name, rating=c.rating, positions=tuple(c.positions or ()),
        nation=c.nation_id, league=c.league_id, club=c.club_id,
        rarity="common" if c.rarity == "unknown" else c.rarity, kind=kind,
        owned=owned is not None, untradeable=bool(owned and owned.untradeable),
        price=price.price if price else None,
    )


def cards_for_solve(db: Session, user: User | None, platform: str = "console",
                    include_market: bool = True) -> tuple[list[SolverCard], dict[str, Price]]:
    """All cards the solver may use: the user's club plus (optionally) buyable market cards.

    Returns the cards and a map card-id -> Price row (for labelling live/estimate in the UI).
    Loan items are excluded (they cannot be submitted to SBCs).
    """
    cards = {c.definition_id: c for c in db.scalars(select(Card))}
    prices = {p.definition_id: p for p in db.scalars(select(Price).where(Price.platform == platform))}
    out, price_of = [], {}
    if user is not None:
        for ci in db.scalars(select(ClubItem).where(ClubItem.user_id == user.id)):
            c = cards.get(ci.definition_id)
            if c is None or ci.loans:
                continue
            sc = _solver_card(c, prices.get(c.definition_id), ci)
            out.append(sc)
            if c.definition_id in prices:
                price_of[sc.id] = prices[c.definition_id]
    if include_market:
        for did, c in cards.items():
            p = prices.get(did)
            if p is None:
                continue
            if c.rarity not in ("common", "rare", "unknown") and p.source != "live":
                continue  # never plan to buy specials (icons, TOTW, ...) on a guessed price
            sc = _solver_card(c, p, None)
            out.append(sc)
            price_of[sc.id] = p
    return out, price_of
