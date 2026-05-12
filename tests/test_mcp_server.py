"""Tests for the read-only MCP server (SCI-0504)."""

from __future__ import annotations

import agt.mcp_server as mcp_module


def test_mcp_server_instantiated() -> None:
    assert mcp_module.mcp is not None
    assert mcp_module.mcp.name == "SciAgent"


def test_mcp_tools_registered() -> None:
    tool_names = {t.name for t in mcp_module.mcp._tool_manager.list_tools()}  # type: ignore[reportPrivateUsage]
    expected = {"search_papers", "list_watches", "get_session", "library_doctor"}
    assert expected == tool_names


def test_mcp_no_write_tools() -> None:
    tool_names = {t.name for t in mcp_module.mcp._tool_manager.list_tools()}  # type: ignore[reportPrivateUsage]
    write_patterns = {"write", "upsert", "resume", "approve", "delete", "create"}
    for name in tool_names:
        for pattern in write_patterns:
            assert pattern not in name.lower(), f"Write tool found: {name}"
