from __future__ import annotations

import pytest

from agt.tools.arxiv_api import ArxivClient, ArxivResponseError


@pytest.mark.anyio
async def test_arxiv_normalizes_feed(monkeypatch: pytest.MonkeyPatch) -> None:
    client = ArxivClient(timeout_seconds=5, retries=1)

    async def _fake_request_text(*, query: dict[str, str]) -> str:
        _ = query
        return """
<feed xmlns='http://www.w3.org/2005/Atom'>
  <entry>
    <id>http://arxiv.org/abs/2501.00001</id>
    <title>  Test Title </title>
    <summary>Abstract text</summary>
    <published>2025-01-01T00:00:00Z</published>
    <author><name>Ada</name></author>
  </entry>
</feed>
"""

    monkeypatch.setattr(client, "_request_text", _fake_request_text)
    papers = await client.search("query", limit=5)
    assert len(papers) == 1
    assert papers[0].arxiv_id == "2501.00001"
    assert papers[0].open_access is True


@pytest.mark.anyio
async def test_arxiv_passes_categories(monkeypatch: pytest.MonkeyPatch) -> None:
    client = ArxivClient(timeout_seconds=5, retries=1)
    seen: dict[str, str] = {}

    async def _fake_request_text(*, query: dict[str, str]) -> str:
        seen.update(query)
        return "<feed xmlns='http://www.w3.org/2005/Atom'></feed>"

    monkeypatch.setattr(client, "_request_text", _fake_request_text)
    papers = await client.search("query", limit=5, categories=["cs.CL"])
    assert papers == []
    assert "cat:cs.CL" in seen["search_query"]


@pytest.mark.anyio
async def test_arxiv_raises_on_bad_xml(monkeypatch: pytest.MonkeyPatch) -> None:
    client = ArxivClient(timeout_seconds=5, retries=1)

    async def _fake_request_text(*, query: dict[str, str]) -> str:
        _ = query
        return "<not-xml"

    monkeypatch.setattr(client, "_request_text", _fake_request_text)
    with pytest.raises(ArxivResponseError):
        await client.search("query", limit=5)
