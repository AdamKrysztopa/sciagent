"""SQLite-backed result cache with configurable TTL (SCI-0204)."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from pathlib import Path
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS cache_entries (
    cache_key TEXT PRIMARY KEY,
    query     TEXT NOT NULL,
    data      TEXT NOT NULL,
    created   REAL NOT NULL
);
"""


class ResultCache:
    """Thread-safe SQLite cache for search results."""

    def __init__(self, cache_dir: Path, ttl_seconds: int) -> None:
        cache_dir.mkdir(parents=True, exist_ok=True)
        self._path = str(cache_dir / "result_cache.db")
        self._ttl = ttl_seconds
        with self._connect() as conn:
            conn.execute(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _make_key(query: str, hard_filters: dict[str, Any], result_limit: int) -> str:
        canonical = json.dumps(
            {"q": query.strip().lower(), "f": hard_filters, "n": result_limit},
            sort_keys=True,
            ensure_ascii=True,
        )
        return hashlib.sha256(canonical.encode()).hexdigest()

    def get(
        self, query: str, hard_filters: dict[str, Any], result_limit: int
    ) -> dict[str, Any] | None:
        key = self._make_key(query, hard_filters, result_limit)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT data, created FROM cache_entries WHERE cache_key = ?", (key,)
            ).fetchone()
        if row is None:
            return None
        if time.time() - float(row["created"]) > self._ttl:
            with self._connect() as conn:
                conn.execute("DELETE FROM cache_entries WHERE cache_key = ?", (key,))
            return None
        data: dict[str, Any] = json.loads(str(row["data"]))
        return data

    def set(
        self,
        query: str,
        hard_filters: dict[str, Any],
        result_limit: int,
        data: dict[str, Any],
    ) -> None:
        key = self._make_key(query, hard_filters, result_limit)
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO cache_entries (cache_key, query, data, created) "
                "VALUES (?, ?, ?, ?)",
                (key, query.strip()[:500], json.dumps(data, default=str), time.time()),
            )

    def stats(self) -> dict[str, Any]:
        now = time.time()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS total, "
                "SUM(CASE WHEN ? - created > ? THEN 1 ELSE 0 END) AS expired "
                "FROM cache_entries",
                (now, self._ttl),
            ).fetchone()
        total = int(row["total"] or 0)
        expired = int(row["expired"] or 0)
        return {
            "total_entries": total,
            "expired_entries": expired,
            "active_entries": total - expired,
            "ttl_seconds": self._ttl,
        }

    def clear(self, *, expired_only: bool = False) -> int:
        with self._connect() as conn:
            if expired_only:
                cursor = conn.execute(
                    "DELETE FROM cache_entries WHERE ? - created > ?",
                    (time.time(), self._ttl),
                )
            else:
                cursor = conn.execute("DELETE FROM cache_entries")
            return int(cursor.rowcount)
