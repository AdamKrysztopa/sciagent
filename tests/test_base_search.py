from __future__ import annotations

import pytest

from agt.tools.base_search import BaseSearchClient, BaseSearchResponseError


@pytest.mark.anyio
async def test_base_search_normalizes_xml(monkeypatch: pytest.MonkeyPatch) -> None:
    client = BaseSearchClient(timeout_seconds=5, retries=1)

    async def _fake_request_text(*, params: dict[str, str]) -> str:
        _ = params
        return """
<root>
  <record>
    <title>Paper</title>
    <year>2024</year>
    <doi>10.1/abc</doi>
    <creator>Ada</creator>
    <accessRights>open access</accessRights>
  </record>
</root>
"""

    monkeypatch.setattr(client, "_request_text", _fake_request_text)
    papers = await client.search("query", limit=5)
    assert len(papers) == 1
    assert papers[0].open_access is True


@pytest.mark.anyio
async def test_base_search_handles_missing_optional_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    client = BaseSearchClient(timeout_seconds=5, retries=1)

    async def _fake_request_text(*, params: dict[str, str]) -> str:
        _ = params
        return "<root><record><title>Paper</title></record></root>"

    monkeypatch.setattr(client, "_request_text", _fake_request_text)
    papers = await client.search("query", limit=5)
    assert len(papers) == 1
    assert papers[0].authors == []


@pytest.mark.anyio
async def test_base_search_raises_on_bad_xml(monkeypatch: pytest.MonkeyPatch) -> None:
    client = BaseSearchClient(timeout_seconds=5, retries=1)

    async def _fake_request_text(*, params: dict[str, str]) -> str:
        _ = params
        return "<broken"

    monkeypatch.setattr(client, "_request_text", _fake_request_text)
    with pytest.raises(BaseSearchResponseError):
        await client.search("query", limit=5)
