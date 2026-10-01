"""Monotonic change counter used for the frontend's IndexedDB delta sync.

The counter row is locked (SELECT ... FOR UPDATE) once per transaction and then incremented
in memory, so bulk upserts do not issue one locking query per row.
"""
from sqlalchemy import event
from sqlalchemy.orm import Session

from .models import SyncState

_KEY = "_sync_state_row"


def next_version(db: Session) -> int:
    row = db.info.get(_KEY)
    if row is None:
        row = db.get(SyncState, "version", with_for_update=True)
        if row is None:
            row = SyncState(key="version", value=0)
            db.add(row)
        db.info[_KEY] = row
    row.value += 1
    return row.value


def current_version(db: Session) -> int:
    row = db.get(SyncState, "version")
    return row.value if row else 0


@event.listens_for(Session, "after_commit")
@event.listens_for(Session, "after_rollback")
def _forget_lock(session: Session):
    session.info.pop(_KEY, None)
