"""Persistent search session store backed by JSON files (SCI-0203)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast


class SessionStore:
    """File-backed session persistence. Each session is one JSON file."""

    def __init__(self, session_dir: Path) -> None:
        self._dir = session_dir
        self._dir.mkdir(parents=True, exist_ok=True)

    def save(self, session_id: str, state: dict[str, Any]) -> None:
        path = self._dir / f"{session_id}.json"
        payload: dict[str, Any] = {
            "session_id": session_id,
            "saved_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
            "state": state,
        }
        path.write_text(json.dumps(payload, default=str, indent=2), encoding="utf-8")

    def load(self, session_id: str) -> dict[str, Any]:
        path = self._dir / f"{session_id}.json"
        if not path.exists():
            raise KeyError(session_id)
        raw = json.loads(path.read_text(encoding="utf-8"))
        return cast(dict[str, Any], raw)

    def list_sessions(self) -> list[dict[str, Any]]:
        summaries: list[dict[str, Any]] = []
        for path in sorted(
            self._dir.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        ):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                state: dict[str, Any] = payload.get("state") or {}
                metadata: dict[str, Any] = state.get("search_metadata") or {}
                summaries.append({
                    "session_id": payload.get("session_id", path.stem),
                    "saved_at": payload.get("saved_at"),
                    "query": metadata.get("original_query", ""),
                    "paper_count": len(state.get("papers") or []),
                    "phase": state.get("phase", ""),
                })
            except json.JSONDecodeError, OSError, KeyError:
                continue
        return summaries

    def extract_rerun_payload(self, session_id: str) -> dict[str, Any]:
        """Build a RunRequest-compatible payload from a saved session."""
        payload = self.load(session_id)
        state: dict[str, Any] = payload.get("state") or {}
        metadata: dict[str, Any] = state.get("search_metadata") or {}
        search_plan: dict[str, Any] = metadata.get("search_plan") or {}
        query = metadata.get("original_query", "")
        collection_name: str | None = state.get("collection_name")
        hard_filters: dict[str, Any] = search_plan.get("hard_filters") or {}
        soft_prefs: dict[str, Any] = search_plan.get("soft_preferences") or {}
        return {
            "query": query,
            "collection_name": collection_name,
            "filter_edit": {
                "original_query": query,
                "hard_filters": hard_filters,
                "soft_preferences": soft_prefs,
                "result_limit": 10,
            },
        }
