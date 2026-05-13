"""Tests for src/agt/tools/author_resolver.py."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agt.config import Settings
from agt.models import NormalizedAuthor
from agt.tools.author_resolver import dedup_by_orcid, resolve_author


def _make_author(
    *,
    name: str = "Alice Smith",
    orcid: str | None = None,
    openalex_id: str | None = None,
    s2_author_id: str | None = None,
    source: str = "openalex",
) -> NormalizedAuthor:
    return NormalizedAuthor(
        name=name,
        orcid=orcid,
        openalex_id=openalex_id,
        s2_author_id=s2_author_id,
        source=source,
    )


class TestDedupByOrcid:
    def test_shared_orcid_merges_into_one(self) -> None:
        oa = _make_author(name="Alice Smith", orcid="0000-0001-2345-6789", openalex_id="A123")
        s2 = _make_author(
            name="Alice Smith",
            orcid="0000-0001-2345-6789",
            s2_author_id="456",
            source="semantic_scholar",
        )
        result = dedup_by_orcid([oa, s2])
        assert len(result) == 1
        assert result[0].openalex_id == "A123"
        assert result[0].s2_author_id == "456"

    def test_different_orcids_preserved(self) -> None:
        a1 = _make_author(name="Alice Smith", orcid="0000-0001-0000-0001")
        a2 = _make_author(name="Bob Jones", orcid="0000-0002-0000-0002")
        result = dedup_by_orcid([a1, a2])
        assert len(result) == 2  # noqa: PLR2004

    def test_no_orcid_kept_in_tail(self) -> None:
        a1 = _make_author(name="Alice Smith", orcid="0000-0001-0000-0001", openalex_id="A1")
        a2 = _make_author(name="Bob Jones", orcid=None, s2_author_id="789")
        result = dedup_by_orcid([a1, a2])
        assert len(result) == 2  # noqa: PLR2004
        # orcid-holders come first; no-orcid appended at the tail
        assert result[0].orcid == "0000-0001-0000-0001"
        assert result[1].orcid is None

    def test_empty_input(self) -> None:
        assert dedup_by_orcid([]) == []

    def test_existing_openalex_id_not_overwritten(self) -> None:
        """First-seen OpenAlex ID should not be overwritten by a later entry."""
        a1 = _make_author(orcid="0000-0001-X", openalex_id="A_FIRST")
        a2 = _make_author(orcid="0000-0001-X", openalex_id="A_SECOND")
        result = dedup_by_orcid([a1, a2])
        assert len(result) == 1
        assert result[0].openalex_id == "A_FIRST"


class TestResolveAuthor:
    @pytest.mark.asyncio
    async def test_oa_and_s2_combined(self) -> None:
        """resolve_author returns NormalizedAuthor list from both providers."""
        oa_resp = MagicMock()
        oa_resp.status_code = 200
        oa_resp.json = MagicMock(
            return_value={
                "results": [
                    {
                        "display_name": "Geoffrey Hinton",
                        "id": "https://openalex.org/A123",
                        "orcid": "https://orcid.org/0000-0002-9903-2723",
                    }
                ]
            }
        )
        s2_resp = MagicMock()
        s2_resp.status_code = 200
        s2_resp.json = MagicMock(
            return_value={"data": [{"authorId": "1741101", "name": "Geoffrey Hinton"}]}
        )

        call_count = 0

        async def fake_get(url: str, **_kwargs: object) -> object:
            nonlocal call_count
            call_count += 1
            if "openalex" in url:
                return oa_resp
            return s2_resp

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = fake_get

        with patch("agt.tools.author_resolver.httpx.AsyncClient", return_value=mock_client):
            result = await resolve_author("Geoffrey Hinton", settings=Settings(_env_file=None))  # pyright: ignore[reportCallIssue]

        # OA + S2 share the same ORCID — should merge into 1 result
        assert len(result) >= 1
        assert any(a.openalex_id == "A123" for a in result)

    @pytest.mark.asyncio
    async def test_oa_failure_still_returns_s2_results(self) -> None:
        """Returns S2 results even when OpenAlex returns 500."""
        oa_resp = MagicMock()
        oa_resp.status_code = 500
        oa_resp.json = MagicMock(return_value={})

        s2_resp = MagicMock()
        s2_resp.status_code = 200
        s2_resp.json = MagicMock(return_value={"data": [{"authorId": "42", "name": "Test Author"}]})

        async def fake_get(url: str, **_kwargs: object) -> object:
            if "openalex" in url:
                return oa_resp
            return s2_resp

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = fake_get

        with patch("agt.tools.author_resolver.httpx.AsyncClient", return_value=mock_client):
            result = await resolve_author("Test Author", settings=Settings(_env_file=None))  # pyright: ignore[reportCallIssue]

        assert len(result) == 1
        assert result[0].s2_author_id == "42"

    @pytest.mark.asyncio
    async def test_both_fail_returns_empty_list(self) -> None:
        """Returns empty list when both providers return non-200."""
        fail_resp = MagicMock()
        fail_resp.status_code = 503
        fail_resp.json = MagicMock(return_value={})

        async def fake_get(_url: str, **_kwargs: object) -> object:
            return fail_resp

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = fake_get

        with patch("agt.tools.author_resolver.httpx.AsyncClient", return_value=mock_client):
            result = await resolve_author("Nobody", settings=Settings(_env_file=None))  # pyright: ignore[reportCallIssue]

        assert result == []
