"""One way to open the three SQLite databases (archive, newsletter, accounts).

**WAL** (write-ahead log): readers never wait for the writer and the writer never waits for
readers. The API reads while a pipeline run writes, which the default journal turns into
"database is locked". The mode is stored in the file, so it survives restarts; a database that
cannot switch (a network drive) keeps its mode and still works.

**busy timeout**: a writer that meets another writer waits up to this long instead of failing.
"""

import sqlite3
from pathlib import Path
from typing import Union

BUSY_TIMEOUT_SECONDS = 30


def connect(path: Union[str, Path]) -> sqlite3.Connection:
    conn = sqlite3.connect(path, timeout=BUSY_TIMEOUT_SECONDS)
    conn.row_factory = sqlite3.Row
    conn.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_SECONDS * 1000}")
    try:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")  # safe with WAL: a crash loses at most the last commit, never the file
    except sqlite3.OperationalError:
        pass
    return conn
