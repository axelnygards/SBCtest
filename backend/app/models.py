"""Database tables.

cards              every card we know: base cards from EA's ratings database (definition_id ==
                   base_id) plus special versions first seen through the extension.
price_observations raw, append-only price reports from extensions (crowdsourced).
prices             current price per card: live (aggregated observations) or estimate.
users              anonymous accounts; the extension is paired with a token, never EA login.
club_items         a user's own cards, imported by the extension.
sync_state         monotonic change counter for the frontend's IndexedDB delta sync.
"""
from datetime import datetime, timezone

from sqlalchemy import (JSON, BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String,
                        UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)  # naive UTC everywhere


class League(Base):
    __tablename__ = "leagues"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(String(120))


class Card(Base):
    __tablename__ = "cards"
    definition_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    base_id: Mapped[int] = mapped_column(BigInteger, index=True)
    name: Mapped[str] = mapped_column(String(160))
    rating: Mapped[int] = mapped_column(Integer, index=True)
    positions: Mapped[list] = mapped_column(JSON)
    nation_id: Mapped[int] = mapped_column(Integer, index=True)
    league_id: Mapped[int] = mapped_column(Integer, index=True)
    club_id: Mapped[int] = mapped_column(Integer, index=True)
    gender: Mapped[int] = mapped_column(Integer, default=0)
    rareflag: Mapped[int | None] = mapped_column(Integer, nullable=True)  # None = not yet seen
    rarity: Mapped[str] = mapped_column(String(40), default="unknown")
    kind: Mapped[str] = mapped_column(String(10), default="normal")
    source: Mapped[str] = mapped_column(String(20), default="ea_ratings")
    names: Mapped[dict] = mapped_column(JSON, default=dict)  # nation/club/league labels
    version: Mapped[int] = mapped_column(BigInteger, index=True, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class PriceObservation(Base):
    __tablename__ = "price_observations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    definition_id: Mapped[int] = mapped_column(BigInteger)
    platform: Mapped[str] = mapped_column(String(8), default="console")
    kind: Mapped[str] = mapped_column(String(12))   # bin_min | limit_min | limit_max
    price: Mapped[int] = mapped_column(Integer)
    sample_size: Mapped[int] = mapped_column(Integer, default=1)
    reporter: Mapped[str] = mapped_column(String(64))  # hashed user id
    observed_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    __table_args__ = (Index("ix_obs_card_time", "definition_id", "platform", "observed_at"),)


class Price(Base):
    __tablename__ = "prices"
    definition_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    platform: Mapped[str] = mapped_column(String(8), primary_key=True, default="console")
    price: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(10))  # live | estimate | default
    n_obs: Mapped[int] = mapped_column(Integer, default=0)
    min_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    observed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    version: Mapped[int] = mapped_column(BigInteger, index=True, default=0)


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    platform: Mapped[str] = mapped_column(String(8), default="console")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    club_imported_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ClubItem(Base):
    __tablename__ = "club_items"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"),
                                         primary_key=True)
    item_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    definition_id: Mapped[int] = mapped_column(BigInteger, index=True)
    untradeable: Mapped[bool] = mapped_column(Boolean, default=False)
    loans: Mapped[int] = mapped_column(Integer, default=0)
    location: Mapped[str] = mapped_column(String(12), default="club")  # club | storage | unassigned
    __table_args__ = (UniqueConstraint("user_id", "item_id"),)


class SyncState(Base):
    __tablename__ = "sync_state"
    key: Mapped[str] = mapped_column(String(20), primary_key=True)
    value: Mapped[int] = mapped_column(BigInteger, default=0)
