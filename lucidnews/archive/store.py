"""SQLite archive of pipeline runs and processed items.

Every run is recorded with the items it fetched and selected. Items are stored
as their full ``ContentItem`` JSON plus a few indexed columns, so later stages
(weekly digests, source health, retries, corroboration) can query history
without re-fetching or re-analyzing.

The archive is an append/upsert log: an item seen in several runs keeps one row,
updated with its latest processing state.
"""

import hashlib
import json
import sqlite3
import uuid
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

from ..models import ContentItem
from ..sqlite_util import connect
from ..source_health import SourceRunOutcome
from . import search as fts

SCHEMA_VERSION = 6

# last_error of an item left unanalyzed because the AI quota ran out (not a failure).
AI_SKIPPED_PREFIX = "ai_skipped:"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    since TEXT NOT NULL,
    fetched_count INTEGER NOT NULL DEFAULT 0,
    selected_count INTEGER NOT NULL DEFAULT 0,
    fetch_report TEXT,
    error TEXT
);
CREATE TABLE IF NOT EXISTS items (
    id TEXT PRIMARY KEY,
    url TEXT NOT NULL,
    source_type TEXT NOT NULL,
    title TEXT NOT NULL,
    published_at TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    profile TEXT,
    score REAL,
    reliability TEXT,
    categories TEXT NOT NULL DEFAULT '[]',
    payload TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS items_published_at ON items (published_at);
CREATE TABLE IF NOT EXISTS run_items (
    run_id TEXT NOT NULL REFERENCES runs (id),
    item_id TEXT NOT NULL REFERENCES items (id),
    selected INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (run_id, item_id)
);
CREATE INDEX IF NOT EXISTS run_items_item ON run_items (item_id);
CREATE TABLE IF NOT EXISTS source_runs (
    run_id TEXT NOT NULL REFERENCES runs (id),
    source_key TEXT NOT NULL,
    source_type TEXT NOT NULL,
    status TEXT NOT NULL,
    fetched_count INTEGER NOT NULL DEFAULT 0,
    selected_count INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    PRIMARY KEY (run_id, source_key)
);
CREATE INDEX IF NOT EXISTS source_runs_key ON source_runs (source_key);
"""

# Columns added after version 1, applied to existing databases on open.
_MIGRATIONS = {
    "items": {
        "analysis_attempts": "INTEGER NOT NULL DEFAULT 0",  # runs whose analysis failed
        "last_error": "TEXT",
    },
    "runs": {
        "unscored_count": "INTEGER NOT NULL DEFAULT 0",
        # AI availability: why the AI stopped (provider_quota, token_budget) and usage.
        "ai_limit": "TEXT",
        "tokens_used": "INTEGER NOT NULL DEFAULT 0",
        "ai_skipped_count": "INTEGER NOT NULL DEFAULT 0",
        # Selection counters (lot 19). NULL for runs recorded before they existed.
        "url_merged_count": "INTEGER",
        "topic_merged_count": "INTEGER",
        "above_threshold_count": "INTEGER",
    },
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def content_hash(item: ContentItem) -> str:
    """Fingerprint of what the AI sees, used to decide whether an analysis is reusable."""
    basis = json.dumps(
        [item.title, str(item.url), item.content or "", item.profile],
        ensure_ascii=False,
    )
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class RunRecord:
    id: str
    started_at: str
    finished_at: Optional[str]
    status: str
    since: str
    fetched_count: int
    selected_count: int
    error: Optional[str]
    unscored_count: int = 0
    ai_limit: Optional[str] = None
    tokens_used: int = 0
    ai_skipped_count: int = 0
    url_merged_count: Optional[int] = None
    topic_merged_count: Optional[int] = None
    above_threshold_count: Optional[int] = None


RUN_COLUMNS = (
    "id, started_at, finished_at, status, since, fetched_count, selected_count, error, "
    "unscored_count, ai_limit, tokens_used, ai_skipped_count, "
    "url_merged_count, topic_merged_count, above_threshold_count"
)


class ItemArchive:
    """Small synchronous SQLite store; each call opens a short-lived connection."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as conn, conn:
            conn.executescript(_SCHEMA)
            for table, columns in _MIGRATIONS.items():
                existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})")}
                for name, definition in columns.items():
                    if name not in existing:
                        conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")
            conn.execute(
                "INSERT OR REPLACE INTO meta (key, value) VALUES ('schema_version', ?)",
                (str(SCHEMA_VERSION),),
            )
            self.search_available = self._init_search(conn)

    def _init_search(self, conn: sqlite3.Connection) -> bool:
        """Create the full-text index; index the items already archived the first time.

        Returns False when this SQLite has no FTS5: the archive still works, search is off.
        """
        try:
            conn.execute(fts.FTS_SCHEMA)
        except sqlite3.OperationalError:
            return False
        row = conn.execute("SELECT value FROM meta WHERE key = 'fts_version'").fetchone()
        if row is None or row["value"] != fts.INDEX_VERSION:
            fts.rebuild(conn)
        return True

    def _connect(self) -> sqlite3.Connection:
        conn = connect(self.path)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    # Runs -----------------------------------------------------------------

    def start_run(self, since: datetime) -> str:
        run_id = f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:8]}"
        with closing(self._connect()) as conn, conn:
            conn.execute(
                "INSERT INTO runs (id, started_at, status, since) VALUES (?, ?, 'running', ?)",
                (run_id, _now(), _iso(since)),
            )
        return run_id

    def finish_run(
        self,
        run_id: str,
        status: str,
        *,
        fetch_report: Optional[dict] = None,
        error: Optional[str] = None,
        ai_limit: Optional[str] = None,
        tokens_used: int = 0,
    ) -> None:
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """UPDATE runs SET finished_at = ?, status = ?, error = ?,
                       ai_limit = ?, tokens_used = ?,
                       ai_skipped_count = (SELECT COUNT(*) FROM run_items JOIN items ON items.id = run_items.item_id
                                           WHERE run_items.run_id = ?
                                             AND json_extract(items.payload, '$.processing.ai_skipped') IS NOT NULL),
                       fetch_report = COALESCE(?, fetch_report),
                       fetched_count = (SELECT COUNT(*) FROM run_items WHERE run_id = ?),
                       selected_count = (SELECT COUNT(*) FROM run_items WHERE run_id = ? AND selected = 1),
                       unscored_count = (SELECT COUNT(*) FROM run_items JOIN items ON items.id = run_items.item_id
                                         WHERE run_items.run_id = ? AND items.score IS NULL)
                   WHERE id = ?""",
                (
                    _now(),
                    status,
                    error,
                    ai_limit,
                    tokens_used,
                    run_id,
                    json.dumps(fetch_report) if fetch_report is not None else None,
                    run_id,
                    run_id,
                    run_id,
                    run_id,
                ),
            )

    def record_selection_stats(
        self, run_id: str, *, url_merged: int, topic_merged: int, above_threshold: int
    ) -> None:
        """Counters of the selection stage, kept for the quality overview."""
        with closing(self._connect()) as conn, conn:
            conn.execute(
                """UPDATE runs SET url_merged_count = ?, topic_merged_count = ?, above_threshold_count = ?
                   WHERE id = ?""",
                (url_merged, topic_merged, above_threshold, run_id),
            )

    def runs_since(self, since: datetime) -> List[RunRecord]:
        """Finished runs started since ``since``, oldest first."""
        with closing(self._connect()) as conn:
            rows = conn.execute(
                f"""SELECT {RUN_COLUMNS} FROM runs WHERE started_at >= ? AND status != 'running'
                    ORDER BY started_at""",
                (_iso(since),),
            ).fetchall()
        return [RunRecord(**dict(row)) for row in rows]

    def published_since(self, since: datetime) -> List[tuple[str, ContentItem]]:
        """(run start, item) for every item published by a successful run started since ``since``."""
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """SELECT r.started_at, i.payload FROM run_items ri
                   JOIN runs r ON r.id = ri.run_id JOIN items i ON i.id = ri.item_id
                   WHERE ri.selected = 1 AND r.status = 'success' AND r.started_at >= ?
                   ORDER BY r.started_at""",
                (_iso(since),),
            ).fetchall()
        return [(row["started_at"], ContentItem.model_validate_json(row["payload"])) for row in rows]

    def get_run(self, run_id: str) -> Optional[RunRecord]:
        with closing(self._connect()) as conn:
            row = conn.execute(
                f"""SELECT {RUN_COLUMNS} FROM runs WHERE id = ?""",
                (run_id,),
            ).fetchone()
        return RunRecord(**dict(row)) if row else None

    def list_runs(self, limit: int = 20) -> List[RunRecord]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                f"""SELECT {RUN_COLUMNS} FROM runs ORDER BY started_at DESC LIMIT ?""",
                (limit,),
            ).fetchall()
        return [RunRecord(**dict(row)) for row in rows]

    def latest_published_run(self) -> Optional[RunRecord]:
        """Most recent successful run that selected at least one item."""
        with closing(self._connect()) as conn:
            row = conn.execute(
                f"""SELECT {RUN_COLUMNS} FROM runs
                   WHERE status = 'success' AND selected_count > 0
                   ORDER BY started_at DESC LIMIT 1"""
            ).fetchone()
        return RunRecord(**dict(row)) if row else None

    def runs_selecting(self, item_id: str) -> List[RunRecord]:
        """Successful runs that published the item, newest first."""
        with closing(self._connect()) as conn:
            rows = conn.execute(
                f"""SELECT {', '.join('r.' + column for column in RUN_COLUMNS.split(', '))}
                   FROM runs r JOIN run_items ri ON ri.run_id = r.id
                   WHERE ri.item_id = ? AND ri.selected = 1 AND r.status = 'success'
                   ORDER BY r.started_at DESC""",
                (item_id,),
            ).fetchall()
        return [RunRecord(**dict(row)) for row in rows]

    def run_item_ids(self, run_id: str, *, selected_only: bool = False) -> List[str]:
        query = "SELECT item_id FROM run_items WHERE run_id = ?"
        if selected_only:
            query += " AND selected = 1"
        with closing(self._connect()) as conn:
            return [row["item_id"] for row in conn.execute(query, (run_id,))]

    # Items ----------------------------------------------------------------

    def record_items(
        self,
        run_id: str,
        items: Iterable[ContentItem],
        *,
        selected: bool = False,
    ) -> None:
        """Upsert items with their current processing state and link them to the run."""
        now = _now()
        rows = []
        links = []
        outcomes = []
        for item in items:
            processing = item.processing
            analysis = processing.analysis if processing else None
            reliability = processing.reliability if processing else None
            rows.append(
                (
                    item.id,
                    str(item.url),
                    item.source_type.value,
                    item.title,
                    _iso(item.published_at),
                    now,
                    now,
                    content_hash(item),
                    processing.classification.profile if processing else None,
                    analysis.score if analysis else None,
                    reliability.label.value if reliability else None,
                    json.dumps(analysis.categories if analysis else []),
                    item.model_dump_json(),
                )
            )
            links.append((run_id, item.id, int(selected)))
            if analysis is not None:
                failed = analysis.score is None
                outcomes.append((item.id, int(failed), analysis.reason if failed else None))
            elif processing is not None and processing.ai_skipped is not None:
                # Not a failure: no attempt is used, but the item is retried later.
                outcomes.append((item.id, 0, AI_SKIPPED_PREFIX + processing.ai_skipped.value))
        if not rows:
            return
        with closing(self._connect()) as conn, conn:
            conn.executemany(
                """INSERT OR IGNORE INTO items (id, url, source_type, title, published_at,
                       first_seen_at, last_seen_at, content_hash, profile, score, reliability,
                       categories, payload)
                   VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12, ?13)""",
                rows,
            )
            # Refresh existing rows, but never replace a stored analysis with an
            # unanalyzed copy of the same content (e.g. a re-fetch before analysis).
            conn.executemany(
                """UPDATE items SET
                       url = ?2, source_type = ?3, title = ?4, published_at = ?5,
                       last_seen_at = ?7, content_hash = ?8, profile = ?9, score = ?10,
                       reliability = ?11, categories = ?12, payload = ?13
                   WHERE id = ?1
                     AND NOT (?10 IS NULL AND score IS NOT NULL AND content_hash = ?8)""",
                rows,
            )
            conn.executemany(
                "UPDATE items SET last_seen_at = ?2 WHERE id = ?1",
                [(row[0], row[6]) for row in rows],
            )
            # Count failed analysis attempts; a successful analysis clears the error.
            conn.executemany(
                """UPDATE items SET analysis_attempts = analysis_attempts + ?2, last_error = ?3
                   WHERE id = ?1""",
                outcomes,
            )
            conn.executemany(
                """INSERT INTO run_items (run_id, item_id, selected) VALUES (?, ?, ?)
                   ON CONFLICT (run_id, item_id) DO UPDATE SET
                       selected = MAX(run_items.selected, excluded.selected)""",
                links,
            )
            if self.search_available:
                # Index what is stored (an unanalyzed copy never replaced an analysis above).
                ids = [row[0] for row in rows]
                for start in range(0, len(ids), 500):
                    chunk = ids[start : start + 500]
                    marks = ",".join("?" * len(chunk))
                    stored = conn.execute(f"SELECT payload FROM items WHERE id IN ({marks})", chunk).fetchall()
                    fts.reindex(conn, (ContentItem.model_validate_json(r["payload"]) for r in stored))

    def get_item(self, item_id: str) -> Optional[ContentItem]:
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT payload FROM items WHERE id = ?", (item_id,)).fetchone()
        return ContentItem.model_validate_json(row["payload"]) if row else None

    def get_items(self, item_ids: Sequence[str]) -> dict[str, ContentItem]:
        if not item_ids:
            return {}
        result: dict[str, ContentItem] = {}
        with closing(self._connect()) as conn:
            for start in range(0, len(item_ids), 500):
                chunk = list(item_ids[start : start + 500])
                placeholders = ",".join("?" * len(chunk))
                for row in conn.execute(
                    f"SELECT id, payload FROM items WHERE id IN ({placeholders})", chunk
                ):
                    result[row["id"]] = ContentItem.model_validate_json(row["payload"])
        return result

    def all_items(self) -> List[ContentItem]:
        with closing(self._connect()) as conn:
            rows = conn.execute("SELECT payload FROM items ORDER BY published_at").fetchall()
        return [ContentItem.model_validate_json(row["payload"]) for row in rows]

    def search(self, terms: Sequence[str], limit: int = fts.CANDIDATE_CAP) -> List[tuple[ContentItem, float]]:
        """Items matching every word (as a prefix), best match first, with their rank.

        Raises ``RuntimeError`` when the index is unavailable (SQLite without FTS5).
        """
        if not self.search_available:
            raise RuntimeError("full-text search is not available (SQLite without FTS5)")
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT items.payload AS payload, bm25(items_fts, 4.0, 1.0) AS rank "
                "FROM items_fts JOIN items ON items.id = items_fts.item_id WHERE items_fts MATCH ? "
                "ORDER BY rank, items.published_at DESC LIMIT ?",
                (fts.match_expression(terms), limit),
            ).fetchall()
        return [(ContentItem.model_validate_json(row["payload"]), row["rank"]) for row in rows]

    def update_reliability(self, items: Iterable[ContentItem]) -> int:
        """Store a new reliability assessment for items; nothing else changes."""
        rows = [
            (item.processing.reliability.label.value, item.model_dump_json(), item.id)
            for item in items
            if item.processing and item.processing.reliability
        ]
        if not rows:
            return 0
        with closing(self._connect()) as conn, conn:
            conn.executemany("UPDATE items SET reliability = ?, payload = ? WHERE id = ?", rows)
        return len(rows)

    # Source health ---------------------------------------------------------

    def record_source_runs(self, run_id: str, outcomes: Iterable[SourceRunOutcome]) -> None:
        rows = [
            (
                run_id,
                outcome.source_key,
                outcome.source_type,
                outcome.status,
                outcome.fetched_count,
                outcome.selected_count,
                outcome.error,
            )
            for outcome in outcomes
        ]
        if not rows:
            return
        with closing(self._connect()) as conn, conn:
            conn.executemany(
                """INSERT OR REPLACE INTO source_runs (run_id, source_key, source_type, status,
                       fetched_count, selected_count, error)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                rows,
            )

    def source_run_rows(self, since: datetime) -> List[dict]:
        """Per-source outcomes of finished runs started since ``since``, newest first."""
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """SELECT s.source_key, s.source_type, s.status, s.fetched_count,
                          s.selected_count, s.error, r.started_at
                   FROM source_runs s JOIN runs r ON r.id = s.run_id
                   WHERE r.started_at >= ? AND r.status != 'running'
                   ORDER BY r.started_at DESC""",
                (_iso(since),),
            ).fetchall()
        return [dict(row) for row in rows]

    def pending_items(
        self,
        *,
        first_seen_after: datetime,
        max_attempts: int,
        exclude_ids: Iterable[str] = (),
    ) -> List[ContentItem]:
        """Items to analyze again, oldest first.

        Those whose analysis failed and that still have attempts left, and those left
        unanalyzed because the AI quota ran out (which uses no attempt).
        """
        excluded = set(exclude_ids)
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """SELECT id, payload FROM items
                   WHERE score IS NULL AND analysis_attempts < ?
                     AND (analysis_attempts >= 1 OR last_error LIKE ?)
                     AND first_seen_at >= ?
                   ORDER BY first_seen_at""",
                (max_attempts, AI_SKIPPED_PREFIX + "%", _iso(first_seen_after)),
            ).fetchall()
        return [
            ContentItem.model_validate_json(row["payload"])
            for row in rows
            if row["id"] not in excluded
        ]

    def item_attempts(self, item_id: str) -> tuple[int, Optional[str]]:
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT analysis_attempts, last_error FROM items WHERE id = ?", (item_id,)
            ).fetchone()
        return (row["analysis_attempts"], row["last_error"]) if row else (0, None)

    def items_between(
        self,
        since: datetime,
        until: Optional[datetime] = None,
        *,
        selected_only: bool = False,
    ) -> List[ContentItem]:
        """Items published in [since, until), best score first."""
        query = "SELECT payload FROM items WHERE published_at >= ?"
        params: list[object] = [_iso(since)]
        if until is not None:
            query += " AND published_at < ?"
            params.append(_iso(until))
        if selected_only:
            query += " AND id IN (SELECT item_id FROM run_items WHERE selected = 1)"
        query += " ORDER BY score IS NULL, score DESC, published_at DESC"
        with closing(self._connect()) as conn:
            rows = conn.execute(query, params).fetchall()
        return [ContentItem.model_validate_json(row["payload"]) for row in rows]
