"""SQLite store of accounts and sessions (``data/auth.sqlite3``).

A session token is random and only its SHA-256 is stored, so a copy of the database cannot be
replayed as a cookie.

Every account has a role: ``admin`` runs the newsroom (settings, sources, quality, subscribers,
runs), ``reader`` only reads. Accounts made from the web app are readers; administrators are made
with ``lucidnews-users``.
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
    role TEXT NOT NULL DEFAULT 'reader' CHECK (role IN ('admin', 'reader')),
    created_at TEXT NOT NULL,
    last_login_at TEXT
);
CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    device TEXT
);
CREATE INDEX IF NOT EXISTS sessions_by_user ON sessions (user_id);
CREATE TABLE IF NOT EXISTS reader_preferences (
    user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    data TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""
# A session in use is extended at most this often (a write per request would be wasteful).
REFRESH_AFTER = timedelta(hours=12)
ADMIN, READER = "admin", "reader"
SESSION_ID_LENGTH = 16
ROLES = (ADMIN, READER)


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
    role: str = READER

    @property
    def is_admin(self) -> bool:
        return self.role == ADMIN

    def public(self) -> dict:
        """What the web app may know: never the hash or the Google subject."""
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "picture": self.picture,
            "has_password": self.has_password,
            "has_google": self.google_sub is not None,
            "role": self.role,
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
        role=row["role"],
    )


class AuthDB:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as conn, conn:
            conn.executescript(SCHEMA)
            self._migrate(conn)
        try:
            self.path.chmod(0o600)  # accounts are personal data
        except OSError:
            pass

    @staticmethod
    def _migrate(conn: sqlite3.Connection) -> None:
        """Columns added after the first release. Accounts made before roles existed: the oldest
        one, made by the operator, becomes admin."""
        if "device" not in {row["name"] for row in conn.execute("PRAGMA table_info(sessions)")}:
            conn.execute("ALTER TABLE sessions ADD COLUMN device TEXT")
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
        if "role" in columns:
            return
        conn.execute(
            "ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'reader' CHECK (role IN ('admin', 'reader'))"
        )
        conn.execute("UPDATE users SET role = 'admin' WHERE id = (SELECT id FROM users ORDER BY created_at LIMIT 1)")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    # Users ----------------------------------------------------------------------------------

    def create_user(
        self,
        email: str,
        name: str,
        *,
        password_hash: Optional[str] = None,
        google_sub: Optional[str] = None,
        picture: Optional[str] = None,
        role: str = READER,
    ) -> Optional[User]:
        """None when the address is already taken."""
        if role not in ROLES:
            raise ValueError(f"unknown role: {role}")
        user_id = uuid.uuid4().hex
        with self._lock, closing(self._connect()) as conn, conn:
            try:
                conn.execute(
                    "INSERT INTO users (id, email, name, password_hash, google_sub, picture, role, created_at, last_login_at)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (user_id, email, name, password_hash, google_sub, picture, role, _iso(_now()), _iso(_now())),
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

    def set_role(self, user_id: str, role: str) -> None:
        if role not in ROLES:
            raise ValueError(f"unknown role: {role}")
        with self._lock, closing(self._connect()) as conn, conn:
            conn.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))

    def count_admins(self) -> int:
        with closing(self._connect()) as conn:
            return conn.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'").fetchone()[0]

    def set_password(self, user_id: str, password_hash: str) -> None:
        """New password; every session of the account ends."""
        with self._lock, closing(self._connect()) as conn, conn:
            conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user_id))
            conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))

    def touch_login(self, user_id: str) -> None:
        with self._lock, closing(self._connect()) as conn, conn:
            conn.execute("UPDATE users SET last_login_at = ? WHERE id = ?", (_iso(_now()), user_id))

    # Sessions -------------------------------------------------------------------------------

    def create_session(self, user_id: str, days: int, device: Optional[str] = None) -> str:
        """``device``: a short label such as "Firefox · macOS", shown in the account's session list."""
        token = secrets.token_urlsafe(32)
        now = _now()
        with self._lock, closing(self._connect()) as conn, conn:
            conn.execute("DELETE FROM sessions WHERE expires_at < ?", (_iso(now),))  # housekeeping
            conn.execute(
                "INSERT INTO sessions (token_hash, user_id, created_at, expires_at, last_seen_at, device) VALUES (?, ?, ?, ?, ?, ?)",
                (_hash(token), user_id, _iso(now), _iso(now + timedelta(days=days)), _iso(now), device),
            )
        return token

    def list_sessions(self, user_id: str) -> list[dict]:
        """Live sessions of an account, most recent first. ``id`` is a prefix of the token's hash:
        enough to name a session, useless as a cookie."""
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT token_hash, created_at, last_seen_at, expires_at, device FROM sessions"
                " WHERE user_id = ? AND expires_at > ? ORDER BY last_seen_at DESC",
                (user_id, _iso(_now())),
            ).fetchall()
        return [
            {
                "id": row["token_hash"][:SESSION_ID_LENGTH],
                "created_at": row["created_at"],
                "last_seen_at": row["last_seen_at"],
                "expires_at": row["expires_at"],
                "device": row["device"],
            }
            for row in rows
        ]

    def delete_session_by_id(self, user_id: str, session_id: str) -> bool:
        """End one session of this account, named by ``list_sessions``' id."""
        if len(session_id) != SESSION_ID_LENGTH or not all(c in "0123456789abcdef" for c in session_id):
            return False
        with self._lock, closing(self._connect()) as conn, conn:
            return (
                conn.execute(
                    "DELETE FROM sessions WHERE user_id = ? AND substr(token_hash, 1, ?) = ?",
                    (user_id, SESSION_ID_LENGTH, session_id),
                ).rowcount
                > 0
            )

    def delete_other_sessions(self, user_id: str, keep_token: str) -> int:
        with self._lock, closing(self._connect()) as conn, conn:
            return conn.execute(
                "DELETE FROM sessions WHERE user_id = ? AND token_hash != ?", (user_id, _hash(keep_token))
            ).rowcount

    def password_hash(self, user_id: str) -> Optional[str]:
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT password_hash FROM users WHERE id = ?", (user_id,)).fetchone()
        return row["password_hash"] if row else None

    def rename(self, user_id: str, name: str) -> None:
        with self._lock, closing(self._connect()) as conn, conn:
            conn.execute("UPDATE users SET name = ? WHERE id = ?", (name, user_id))

    def change_password(self, user_id: str, password_hash: str, keep_token: str) -> None:
        """New password from the app: every other session of the account ends, this one stays."""
        with self._lock, closing(self._connect()) as conn, conn:
            conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user_id))
            conn.execute("DELETE FROM sessions WHERE user_id = ? AND token_hash != ?", (user_id, _hash(keep_token)))

    def account_row(self, user_id: str) -> Optional[dict]:
        """Dates the export carries beside the public fields."""
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT created_at, last_login_at FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None

    # Reader preferences (lot 29) --------------------------------------------------------------

    def preferences(self, user_id: str) -> Optional[tuple[str, str]]:
        """The stored JSON and when it was saved; None before the first save."""
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT data, updated_at FROM reader_preferences WHERE user_id = ?", (user_id,)).fetchone()
        return (row["data"], row["updated_at"]) if row else None

    def save_preferences(self, user_id: str, data: str) -> str:
        now = _iso(_now())
        with self._lock, closing(self._connect()) as conn, conn:
            conn.execute(
                "INSERT INTO reader_preferences (user_id, data, updated_at) VALUES (?, ?, ?)"
                " ON CONFLICT(user_id) DO UPDATE SET data = excluded.data, updated_at = excluded.updated_at",
                (user_id, data, now),
            )
        return now

    @staticmethod
    def session_id(token: str) -> str:
        return _hash(token)[:SESSION_ID_LENGTH]

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
