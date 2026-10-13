"""SQLite store of accounts and sessions (``data/auth.sqlite3``).

A session token is random and only its SHA-256 is stored, so a copy of the database cannot be
replayed as a cookie.
"""

import hashlib
import secrets
import sqlite3
import threading
import uuid
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
    name TEXT NOT NULL,
    password_hash TEXT,
    google_sub TEXT UNIQUE,
    picture TEXT,
    created_at TEXT NOT NULL,
    last_login_at TEXT
);
CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS sessions_by_user ON sessions (user_id);
"""
# A session in use is extended at most this often (a write per request would be wasteful).
REFRESH_AFTER = timedelta(hours=12)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(moment: datetime) -> str:
    return moment.isoformat()


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class User:
    id: str
    email: str
    name: str
    has_password: bool
    google_sub: Optional[str]
    picture: Optional[str]
    created_at: str

    def public(self) -> dict:
        """What the web app may know: never the hash or the Google subject."""
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "picture": self.picture,
            "has_password": self.has_password,
            "has_google": self.google_sub is not None,
        }


def _user(row: sqlite3.Row) -> User:
    return User(
        id=row["id"],
        email=row["email"],
        name=row["name"],
        has_password=bool(row["password_hash"]),
        google_sub=row["google_sub"],
        picture=row["picture"],
        created_at=row["created_at"],
    )


class AuthDB:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as conn, conn:
            conn.executescript(SCHEMA)
        try:
            self.path.chmod(0o600)  # accounts are personal data
        except OSError:
            pass

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    # Users ----------------------------------------------------------------------------------

    def create_user(
        self, email: str, name: str, *, password_hash: Optional[str] = None, google_sub: Optional[str] = None, picture: Optional[str] = None
    ) -> Optional[User]:
        """None when the address is already taken."""
        user_id = uuid.uuid4().hex
        with self._lock, closing(self._connect()) as conn, conn:
            try:
                conn.execute(
                    "INSERT INTO users (id, email, name, password_hash, google_sub, picture, created_at, last_login_at)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (user_id, email, name, password_hash, google_sub, picture, _iso(_now()), _iso(_now())),
                )
            except sqlite3.IntegrityError:
                return None
        return self.get(user_id)

    def get(self, user_id: str) -> Optional[User]:
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return _user(row) if row else None

    def by_email(self, email: str) -> Optional[tuple[User, Optional[str]]]:
        """The user and their password hash (only the auth service ever sees the hash)."""
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        return (_user(row), row["password_hash"]) if row else None

    def by_google_sub(self, sub: str) -> Optional[User]:
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT * FROM users WHERE google_sub = ?", (sub,)).fetchone()
        return _user(row) if row else None

    def link_google(self, user_id: str, sub: str, picture: Optional[str]) -> None:
        """Attach a Google identity and remove the password: see ``AuthService`` for why."""
        with self._lock, closing(self._connect()) as conn, conn:
            conn.execute(
                "UPDATE users SET google_sub = ?, picture = COALESCE(?, picture), password_hash = NULL WHERE id = ?",
                (sub, picture, user_id),
            )

    def list_users(self) -> list[User]:
        with closing(self._connect()) as conn:
            rows = conn.execute("SELECT * FROM users ORDER BY created_at, email").fetchall()
        return [_user(row) for row in rows]

    def delete_user(self, user_id: str) -> bool:
        """Remove the account; its sessions go with it (foreign key cascade)."""
        with self._lock, closing(self._connect()) as conn, conn:
            return conn.execute("DELETE FROM users WHERE id = ?", (user_id,)).rowcount == 1

    def set_password(self, user_id: str, password_hash: str) -> None:
        """New password; every session of the account ends."""
        with self._lock, closing(self._connect()) as conn, conn:
            conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user_id))
            conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))

    def touch_login(self, user_id: str) -> None:
        with self._lock, closing(self._connect()) as conn, conn:
            conn.execute("UPDATE users SET last_login_at = ? WHERE id = ?", (_iso(_now()), user_id))

    # Sessions -------------------------------------------------------------------------------

    def create_session(self, user_id: str, days: int) -> str:
        token = secrets.token_urlsafe(32)
        now = _now()
        with self._lock, closing(self._connect()) as conn, conn:
            conn.execute("DELETE FROM sessions WHERE expires_at < ?", (_iso(now),))  # housekeeping
            conn.execute(
                "INSERT INTO sessions (token_hash, user_id, created_at, expires_at, last_seen_at) VALUES (?, ?, ?, ?, ?)",
                (_hash(token), user_id, _iso(now), _iso(now + timedelta(days=days)), _iso(now)),
            )
        return token

    def session_user(self, token: str, days: int) -> Optional[User]:
        """The user of a live session; a session in use slides forward, an expired one is gone."""
        digest = _hash(token)
        now = _now()
        with self._lock, closing(self._connect()) as conn, conn:
            row = conn.execute(
                "SELECT s.expires_at, s.last_seen_at, u.* FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.token_hash = ?",
                (digest,),
            ).fetchone()
            if row is None:
                return None
            if datetime.fromisoformat(row["expires_at"]) <= now:
                conn.execute("DELETE FROM sessions WHERE token_hash = ?", (digest,))
                return None
            if now - datetime.fromisoformat(row["last_seen_at"]) >= REFRESH_AFTER:
                conn.execute(
                    "UPDATE sessions SET last_seen_at = ?, expires_at = ? WHERE token_hash = ?",
                    (_iso(now), _iso(now + timedelta(days=days)), digest),
                )
        return _user(row)

    def delete_session(self, token: str) -> None:
        with self._lock, closing(self._connect()) as conn, conn:
            conn.execute("DELETE FROM sessions WHERE token_hash = ?", (_hash(token),))

    def delete_user_sessions(self, user_id: str) -> None:
        with self._lock, closing(self._connect()) as conn, conn:
            conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
