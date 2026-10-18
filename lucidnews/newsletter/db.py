"""SQLite store of subscribers and of every send (``data/newsletter.sqlite3``).

Replaces ``subscribers.json``. The first time the database is opened empty next to a
``subscribers.json``, its readers are imported (as confirmed: they were already receiving,
and no consent record exists to ask them again) and the file is renamed
``subscribers.json.migrated``, never deleted.

The interface of ``SubscriberStore`` (load, save, get, add, remove) is kept, plus the
operations double opt-in needs.
"""

import json
import logging
import sqlite3
import threading
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from pydantic import ValidationError

from ..sqlite_util import connect
from .models import DigestPreferences, Subscriber, SubscriptionStatus, subscriber_id
from .store import SubscriberStore

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1
SCHEMA = """
CREATE TABLE IF NOT EXISTS subscribers (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
    plan TEXT NOT NULL,
    preferences TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    confirmed_at TEXT,
    unsubscribed_at TEXT
);
CREATE TABLE IF NOT EXISTS deliveries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subscriber_id TEXT NOT NULL,
    email TEXT NOT NULL,
    kind TEXT NOT NULL,
    subject TEXT NOT NULL,
    reference TEXT,
    status TEXT NOT NULL,
    error TEXT,
    provider_id TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS deliveries_by_subscriber ON deliveries (subscriber_id, id DESC);
"""

KINDS = ("confirmation", "daily", "weekly")
MAX_ERROR_LENGTH = 300


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class Delivery:
    id: int
    subscriber_id: str
    email: str
    kind: str
    subject: str
    reference: Optional[str]  # edition id (daily) or first day of the week (weekly)
    status: str  # sent | failed
    error: Optional[str]
    provider_id: Optional[str]
    created_at: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "subscriber_id": self.subscriber_id,
            "email": self.email,
            "kind": self.kind,
            "subject": self.subject,
            "reference": self.reference,
            "status": self.status,
            "error": self.error,
            "created_at": self.created_at,
        }


def _row_to_subscriber(row: sqlite3.Row) -> Optional[Subscriber]:
    try:
        return Subscriber.model_validate(
            {
                "email": row["email"],
                "plan": row["plan"],
                "preferences": json.loads(row["preferences"]),
                "created_at": row["created_at"],
                "status": row["status"],
                "confirmed_at": row["confirmed_at"],
                "unsubscribed_at": row["unsubscribed_at"],
            }
        )
    except (ValidationError, ValueError) as exc:
        logger.warning("Skipping unreadable subscriber row %s: %s", row["id"], exc)
        return None


class SubscriberDB:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as conn, conn:
            conn.executescript(SCHEMA)
            conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        self._migrate_json()

    def _connect(self) -> sqlite3.Connection:
        conn = connect(self.path)
        return conn

    # Migration ----------------------------------------------------------------------------

    def _migrate_json(self) -> None:
        legacy = self.path.parent / "subscribers.json"
        if not legacy.exists():
            return
        with closing(self._connect()) as conn:
            if conn.execute("SELECT COUNT(*) FROM subscribers").fetchone()[0]:
                return  # already in use: the file is not imported over it
        imported = SubscriberStore(legacy).load()
        now = _now()
        with self._lock, closing(self._connect()) as conn, conn:
            for subscriber in imported:
                conn.execute(
                    "INSERT OR IGNORE INTO subscribers (id, email, plan, preferences, status, created_at, confirmed_at, unsubscribed_at)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    self._values(subscriber.model_copy(update={"status": SubscriptionStatus.CONFIRMED, "confirmed_at": subscriber.confirmed_at or None})),
                )
        try:
            legacy.rename(legacy.with_name("subscribers.json.migrated"))
        except OSError as exc:
            logger.warning("Imported %d subscribers but could not rename %s: %s", len(imported), legacy, exc)
        logger.info("Imported %d subscribers from %s at %s", len(imported), legacy, now)

    # Subscribers ----------------------------------------------------------------------------

    @staticmethod
    def _values(subscriber: Subscriber) -> tuple:
        return (
            subscriber.id,
            subscriber.email,
            subscriber.plan.value,
            subscriber.preferences.model_dump_json(),
            subscriber.status.value,
            subscriber.created_at.isoformat(),
            subscriber.confirmed_at.isoformat() if subscriber.confirmed_at else None,
            subscriber.unsubscribed_at.isoformat() if subscriber.unsubscribed_at else None,
        )

    def load(self) -> List[Subscriber]:
        with closing(self._connect()) as conn:
            rows = conn.execute("SELECT * FROM subscribers ORDER BY created_at, email").fetchall()
        return [subscriber for subscriber in (_row_to_subscriber(row) for row in rows) if subscriber is not None]

    def get(self, email: str) -> Optional[Subscriber]:
        return self.get_by_id(subscriber_id(email))

    def get_by_id(self, sub_id: str) -> Optional[Subscriber]:
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT * FROM subscribers WHERE id = ?", (sub_id,)).fetchone()
        return _row_to_subscriber(row) if row else None

    def insert(self, subscriber: Subscriber) -> bool:
        """Add a subscriber; False if the address is already known (whatever its status)."""
        with self._lock, closing(self._connect()) as conn, conn:
            cursor = conn.execute(
                "INSERT OR IGNORE INTO subscribers (id, email, plan, preferences, status, created_at, confirmed_at, unsubscribed_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                self._values(subscriber),
            )
            return cursor.rowcount == 1

    def set_preferences(self, sub_id: str, preferences: DigestPreferences) -> bool:
        with self._lock, closing(self._connect()) as conn, conn:
            return conn.execute("UPDATE subscribers SET preferences = ? WHERE id = ?", (preferences.model_dump_json(), sub_id)).rowcount == 1

    def confirm(self, sub_id: str) -> Optional[Subscriber]:
        """Pending -> confirmed. A reader who left stays out: only a new request brings them back."""
        with self._lock, closing(self._connect()) as conn, conn:
            conn.execute(
                "UPDATE subscribers SET status = 'confirmed', confirmed_at = ? WHERE id = ? AND status = 'pending'",
                (_now(), sub_id),
            )
        return self.get_by_id(sub_id)

    def request_again(self, sub_id: str) -> Optional[Subscriber]:
        """A reader who left asks to come back: pending again, until they confirm."""
        with self._lock, closing(self._connect()) as conn, conn:
            conn.execute(
                "UPDATE subscribers SET status = 'pending', confirmed_at = NULL, unsubscribed_at = NULL"
                " WHERE id = ? AND status = 'unsubscribed'",
                (sub_id,),
            )
        return self.get_by_id(sub_id)

    def unsubscribe(self, sub_id: str) -> Optional[Subscriber]:
        """Any status -> unsubscribed. The address is kept only so it is never mailed again."""
        with self._lock, closing(self._connect()) as conn, conn:
            conn.execute(
                "UPDATE subscribers SET status = 'unsubscribed', unsubscribed_at = COALESCE(unsubscribed_at, ?) WHERE id = ?",
                (_now(), sub_id),
            )
        return self.get_by_id(sub_id)

    def delete(self, sub_id: str) -> bool:
        """Erase the subscriber and their delivery log: nothing is kept."""
        with self._lock, closing(self._connect()) as conn, conn:
            conn.execute("DELETE FROM deliveries WHERE subscriber_id = ?", (sub_id,))
            return conn.execute("DELETE FROM subscribers WHERE id = ?", (sub_id,)).rowcount == 1

    # SubscriberStore compatibility ------------------------------------------------------------

    def save(self, subscribers: Iterable[Subscriber]) -> None:
        """Replace everything with ``subscribers`` (kept for callers of the JSON store)."""
        subscribers = list(subscribers)
        with self._lock, closing(self._connect()) as conn, conn:
            keep = {subscriber.id for subscriber in subscribers}
            for (existing,) in conn.execute("SELECT id FROM subscribers").fetchall():
                if existing not in keep:
                    conn.execute("DELETE FROM subscribers WHERE id = ?", (existing,))
            for subscriber in subscribers:
                conn.execute(
                    "INSERT OR REPLACE INTO subscribers (id, email, plan, preferences, status, created_at, confirmed_at, unsubscribed_at)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    self._values(subscriber),
                )

    def add(self, email: str, preferences: Optional[DigestPreferences] = None, **fields: Any) -> Subscriber:
        """Create a subscriber, or update the preferences of an existing one."""
        subscriber = Subscriber(email=email, preferences=preferences or DigestPreferences(), **fields)
        if not self.insert(subscriber):
            if preferences is not None:
                self.set_preferences(subscriber.id, preferences)
            return self.get_by_id(subscriber.id) or subscriber
        return subscriber

    def remove(self, email: str) -> bool:
        return self.delete(subscriber_id(email))

    # Deliveries -----------------------------------------------------------------------------

    def log_delivery(
        self,
        subscriber: Subscriber,
        kind: str,
        subject: str,
        *,
        ok: bool,
        reference: Optional[str] = None,
        error: Optional[str] = None,
        provider_id: Optional[str] = None,
    ) -> None:
        if kind not in KINDS:
            raise ValueError(f"unknown delivery kind: {kind}")
        with self._lock, closing(self._connect()) as conn, conn:
            conn.execute(
                "INSERT INTO deliveries (subscriber_id, email, kind, subject, reference, status, error, provider_id, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    subscriber.id,
                    subscriber.email,
                    kind,
                    subject,
                    reference,
                    "sent" if ok else "failed",
                    (error or "")[:MAX_ERROR_LENGTH] or None,
                    provider_id,
                    _now(),
                ),
            )

    def deliveries(self, *, subscriber: Optional[str] = None, limit: int = 50) -> List[Delivery]:
        query = "SELECT * FROM deliveries"
        params: list = []
        if subscriber:
            query += " WHERE subscriber_id = ?"
            params.append(subscriber)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        with closing(self._connect()) as conn:
            rows = conn.execute(query, params).fetchall()
        return [
            Delivery(
                id=row["id"],
                subscriber_id=row["subscriber_id"],
                email=row["email"],
                kind=row["kind"],
                subject=row["subject"],
                reference=row["reference"],
                status=row["status"],
                error=row["error"],
                provider_id=row["provider_id"],
                created_at=row["created_at"],
            )
            for row in rows
        ]
