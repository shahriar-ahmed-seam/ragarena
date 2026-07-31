"""SQLite response cache.

Provider calls dominate both the wall-clock time and the bill of a benchmark
run. Caching them keyed by (namespace, model, exact request payload) makes
re-runs near-instant and free, which is what makes iterating on strategies
practical. Cache hits are recorded on the trace so reported latency can be
filtered to cold measurements only.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from .utils import stable_hash

_SCHEMA = """
CREATE TABLE IF NOT EXISTS entries (
    key         TEXT PRIMARY KEY,
    namespace   TEXT NOT NULL,
    model       TEXT NOT NULL,
    value       TEXT NOT NULL,
    created_at  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_entries_namespace ON entries(namespace);
"""


class ResponseCache:
    """Thread-safe, process-local SQLite cache.

    Safe to share across asyncio tasks: every operation takes a lock and uses a
    short-lived cursor, and SQLite is opened with ``check_same_thread=False``
    plus WAL so concurrent readers do not block.
    """

    def __init__(self, directory: Path | str = ".ragarena_cache", enabled: bool = True) -> None:
        self.enabled = enabled
        self.hits = 0
        self.misses = 0
        self._lock = threading.Lock()
        self._conn: sqlite3.Connection | None = None
        self.path = Path(directory) / "responses.sqlite"
        if enabled:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    # ------------------------------------------------------------------ keys
    @staticmethod
    def make_key(namespace: str, model: str, payload: Any) -> str:
        return f"{namespace}:{model}:{stable_hash(payload)}"

    # ------------------------------------------------------------------- api
    def get(self, key: str) -> Any | None:
        if not self.enabled or self._conn is None:
            return None
        with self._lock:
            row = self._conn.execute(
                "SELECT value FROM entries WHERE key = ?", (key,)
            ).fetchone()
        if row is None:
            self.misses += 1
            return None
        self.hits += 1
        try:
            return json.loads(row[0])
        except json.JSONDecodeError:
            return None

    def set(self, key: str, namespace: str, model: str, value: Any) -> None:
        if not self.enabled or self._conn is None:
            return
        blob = json.dumps(value, separators=(",", ":"), default=str)
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO entries (key, namespace, model, value, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (key, namespace, model, blob, time.time()),
            )
            self._conn.commit()

    def stats(self) -> dict[str, int]:
        return {"hits": self.hits, "misses": self.misses}

    def size(self) -> int:
        if not self.enabled or self._conn is None:
            return 0
        with self._lock:
            row = self._conn.execute("SELECT COUNT(*) FROM entries").fetchone()
        return int(row[0]) if row else 0

    def clear(self, namespace: str | None = None) -> int:
        if not self.enabled or self._conn is None:
            return 0
        with self._lock:
            if namespace:
                cur = self._conn.execute(
                    "DELETE FROM entries WHERE namespace = ?", (namespace,)
                )
            else:
                cur = self._conn.execute("DELETE FROM entries")
            self._conn.commit()
            return cur.rowcount or 0

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None

    def __enter__(self) -> ResponseCache:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


class NullCache(ResponseCache):
    """Drop-in cache that never stores anything."""

    def __init__(self) -> None:
        super().__init__(enabled=False)
