"""Persistent watch list store backed by JSON files (SCI-0401)."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass
class Watch:
    id: str
    name: str
    query: str
    collection_name: str | None
    filter_edit: dict[str, Any] | None
    created_at: str
    last_run_at: str | None
    seen_fingerprints: list[str]


class WatchStore:
    """File-backed watch persistence. Each watch is one JSON file."""

    def __init__(self, watch_dir: Path) -> None:
        self._dir = watch_dir
        self._dir.mkdir(parents=True, exist_ok=True)

    def save(self, watch: Watch) -> None:
        path = self._dir / f"{watch.id}.json"
        path.write_text(json.dumps(asdict(watch), indent=2), encoding="utf-8")

    def load(self, watch_id: str) -> Watch:
        path = self._dir / f"{watch_id}.json"
        if not path.exists():
            raise KeyError(watch_id)
        raw = json.loads(path.read_text(encoding="utf-8"))
        return Watch(**raw)

    def delete(self, watch_id: str) -> None:
        path = self._dir / f"{watch_id}.json"
        if not path.exists():
            raise KeyError(watch_id)
        path.unlink()

    def list_watches(self) -> list[Watch]:
        watches: list[Watch] = []
        for path in sorted(
            self._dir.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        ):
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                watches.append(Watch(**raw))
            except json.JSONDecodeError, OSError, TypeError:
                continue
        return watches


def create_watch(
    name: str,
    query: str,
    *,
    collection_name: str | None = None,
    filter_edit: dict[str, Any] | None = None,
) -> Watch:
    """Construct a new Watch with a fresh UUID and empty seen_fingerprints."""
    return Watch(
        id=str(uuid.uuid4()),
        name=name,
        query=query,
        collection_name=collection_name,
        filter_edit=filter_edit,
        created_at=datetime.now(tz=UTC).isoformat(timespec="seconds"),
        last_run_at=None,
        seen_fingerprints=[],
    )
