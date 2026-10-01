"""Monotonic change counter used for the frontend's IndexedDB delta sync."""
from sqlalchemy.orm import Session

from .models import SyncState


def next_version(db: Session) -> int:
    row = db.get(SyncState, "version", with_for_update=True)
    if row is None:
        row = SyncState(key="version", value=0)
        db.add(row)
    row.value += 1
    return row.value


def current_version(db: Session) -> int:
    row = db.get(SyncState, "version")
    return row.value if row else 0
