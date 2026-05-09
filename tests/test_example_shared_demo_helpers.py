from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from examples._shared_demo_helpers import resolve_env_key


def test_resolve_env_key_reads_dotenv_when_process_env_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("AGT_SEMANTIC_SCHOLAR_API_KEY", raising=False)
    monkeypatch.delenv("SEMANTIC_SCHOLAR_API_KEY", raising=False)
    (tmp_path / ".env").write_text('AGT_SEMANTIC_SCHOLAR_API_KEY="ss-from-dotenv"\n')

    resolved = resolve_env_key("AGT_SEMANTIC_SCHOLAR_API_KEY", "SEMANTIC_SCHOLAR_API_KEY")

    assert resolved == "ss-from-dotenv"


def test_resolve_env_key_prefers_process_env_over_dotenv(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AGT_SEMANTIC_SCHOLAR_API_KEY", "ss-from-env")
    (tmp_path / ".env").write_text("AGT_SEMANTIC_SCHOLAR_API_KEY=ss-from-dotenv\n")

    resolved = resolve_env_key("AGT_SEMANTIC_SCHOLAR_API_KEY", "SEMANTIC_SCHOLAR_API_KEY")

    assert resolved == "ss-from-env"
