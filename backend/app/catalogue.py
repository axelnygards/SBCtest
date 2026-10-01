"""In-memory card catalogue per platform: every card, its current price and the buyable
market cards as solver cards.

Loading ~20 000 cards with prices from the database took about a second per solve request
(and blocked the event loop). The catalogue is loaded once and then kept current with delta
queries on the sync version (the counter the frontend's IndexedDB sync uses), at most every
`catalogue_refresh_s` seconds. A database whose version went backwards (reset) is reloaded.
"""
import threading
import time
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .models import Card, Price
from .solver.types import Card as SolverCard, CardKind
from .sync import current_version


@dataclass(frozen=True, slots=True)
class CardRow:
    """Read-only snapshot of a cards row (safe to share between requests)."""
    definition_id: int
    base_id: int
    name: str
    rating: int
    positions: tuple[str, ...]
    nation_id: int
    league_id: int
    club_id: int
    rarity: str
    kind: str
    names: dict

    @classmethod
    def of(cls, c: Card) -> "CardRow":
        return cls(c.definition_id, c.base_id, c.name, c.rating, tuple(c.positions or ()),
                   c.nation_id, c.league_id, c.club_id, c.rarity, c.kind, c.names or {})

    @property
    def is_special(self) -> bool:
        return self.rarity not in ("common", "rare", "unknown")


@dataclass(frozen=True, slots=True)
class PriceInfo:
    definition_id: int
    price: int
    source: str                      # live | estimate | default | own
    observed_at: datetime | None = None

    @classmethod
    def of(cls, p: Price) -> "PriceInfo":
        return cls(p.definition_id, p.price, p.source, p.observed_at)


def solver_card(c: CardRow, price: PriceInfo | None, item_id: int | None = None,
                untradeable: bool = False) -> SolverCard:
    kind = CardKind(c.kind) if c.kind in ("normal", "icon", "hero") else CardKind.NORMAL
    return SolverCard(
        id=f"item:{item_id}" if item_id is not None else f"def:{c.definition_id}",
        base_id=c.base_id, name=c.name, rating=c.rating, positions=c.positions,
        nation=c.nation_id, league=c.league_id, club=c.club_id,
        rarity="common" if c.rarity == "unknown" else c.rarity, kind=kind,
        owned=item_id is not None, untradeable=untradeable,
        price=price.price if price else None)


def buyable(c: CardRow, p: PriceInfo | None) -> bool:
    """Never plan to buy specials (icons, TOTW, ...) on a guessed price."""
    return p is not None and (not c.is_special or p.source in ("live", "own"))


class Catalogue:
    def __init__(self, platform: str):
        self.platform = platform
        self.version = -1
        self.cards: dict[int, CardRow] = {}
        self.prices: dict[int, PriceInfo] = {}
        self._market: dict[int, SolverCard] = {}
        self.market: list[SolverCard] = []
        self._checked = float("-inf")
        self._lock = threading.Lock()

    def refresh(self, db: Session, max_age_s: float | None = None) -> "Catalogue":
        max_age = settings.catalogue_refresh_s if max_age_s is None else max_age_s
        if time.monotonic() - self._checked < max_age:
            return self
        with self._lock:
            if time.monotonic() - self._checked < max_age:
                return self  # another request refreshed while we waited
            v = current_version(db)
            if v < self.version or self.version < 0:
                self._load(db, None)
            elif v != self.version:
                self._load(db, self.version)
            self.version = v
            self._checked = time.monotonic()
        return self

    def in_market(self, definition_id: int) -> bool:
        return definition_id in self._market

    def _load(self, db: Session, since: int | None):
        cq, pq = select(Card), select(Price).where(Price.platform == self.platform)
        if since is not None:
            cq, pq = cq.where(Card.version > since), pq.where(Price.version > since)
        else:
            self.cards, self.prices, self._market = {}, {}, {}
        changed: set[int] = set()
        for c in db.scalars(cq):
            self.cards[c.definition_id] = CardRow.of(c)
            changed.add(c.definition_id)
        for p in db.scalars(pq):
            self.prices[p.definition_id] = PriceInfo.of(p)
            changed.add(p.definition_id)
        for did in changed:
            c, p = self.cards.get(did), self.prices.get(did)
            if c is not None and buyable(c, p):
                self._market[did] = solver_card(c, p)
            else:
                self._market.pop(did, None)
        if changed or since is None:
            self.market = list(self._market.values())  # immutable snapshot for readers


_catalogues: dict[str, Catalogue] = {}
_lock = threading.Lock()


def catalogue(db: Session, platform: str, max_age_s: float | None = None) -> Catalogue:
    with _lock:
        cat = _catalogues.setdefault(platform, Catalogue(platform))
    return cat.refresh(db, max_age_s)


def reset() -> None:
    """Forget all catalogues (tests, or after a manual database import)."""
    with _lock:
        _catalogues.clear()
