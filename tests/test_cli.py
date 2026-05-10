from __future__ import annotations

from argparse import Namespace

import pytest

from agt.graph import cli


class _Parser:
    def parse_args(self) -> Namespace:
        return Namespace(
            query="test query",
            collection="Inbox",
            approve=True,
            thread_id="thread-1",
        )


def _state(phase: str) -> dict[str, object]:
    return {
        "request_id": "req-1",
        "thread_id": "thread-1",
        "messages": ["done"],
        "papers": [],
        "collection_name": "Inbox",
        "approved": True,
        "decision": "approved",
        "phase": phase,
        "selected_indices": [],
        "preflight": {"ok": True},
        "trace_spans": [],
        "write_result": {"created": 0, "unchanged": 0, "failed": 1},
        "search_metadata": None,
    }


@pytest.mark.anyio
async def test_cli_returns_nonzero_for_failed_workflow(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fake_build_parser() -> _Parser:
        return _Parser()

    async def fake_run_workflow(
        query: str,
        collection_name: str,
        approved: bool,
        thread_id: str | None = None,
    ) -> dict[str, object]:
        _ = query
        _ = collection_name
        _ = approved
        _ = thread_id
        return _state("failed")

    monkeypatch.setattr(cli, "build_parser", fake_build_parser)
    monkeypatch.setattr(cli, "run_workflow", fake_run_workflow)

    exit_code = await cli.main()

    assert exit_code == 1
    assert '"phase": "failed"' in capsys.readouterr().out


@pytest.mark.anyio
async def test_cli_returns_zero_for_completed_workflow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_build_parser() -> _Parser:
        return _Parser()

    async def fake_run_workflow(
        query: str,
        collection_name: str,
        approved: bool,
        thread_id: str | None = None,
    ) -> dict[str, object]:
        _ = query
        _ = collection_name
        _ = approved
        _ = thread_id
        return _state("completed")

    monkeypatch.setattr(cli, "build_parser", fake_build_parser)
    monkeypatch.setattr(cli, "run_workflow", fake_run_workflow)

    exit_code = await cli.main()

    assert exit_code == 0
