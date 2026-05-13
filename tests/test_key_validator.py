"""Tests for the provider API key validator."""

from __future__ import annotations

from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from agt.tools.key_validator import KNOWN_PROVIDERS, validate_key

_HTTP_OK = 200
_HTTP_UNAUTHORIZED = 401
_HTTP_FORBIDDEN = 403
_HTTP_INTERNAL_ERROR = 500


def _mock_response(status_code: int) -> MagicMock:
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    return resp


@pytest.mark.anyio
async def test_validate_key_semantic_scholar_200_returns_valid() -> None:
    mock_response = _mock_response(_HTTP_OK)
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("agt.tools.key_validator.httpx.AsyncClient", return_value=mock_client):
        valid, error = await validate_key("semantic_scholar", "s2-test-key")

    assert valid is True
    assert error is None


@pytest.mark.anyio
async def test_validate_key_semantic_scholar_401_returns_invalid() -> None:
    mock_response = _mock_response(_HTTP_UNAUTHORIZED)
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("agt.tools.key_validator.httpx.AsyncClient", return_value=mock_client):
        valid, error = await validate_key("semantic_scholar", "bad-key")

    assert valid is False
    assert error == "invalid_key"


@pytest.mark.anyio
async def test_validate_key_timeout_returns_provider_timeout() -> None:
    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timed out"))

    with patch("agt.tools.key_validator.httpx.AsyncClient", return_value=mock_client):
        valid, error = await validate_key("semantic_scholar", "any-key")

    assert valid is False
    assert error == "provider_timeout"


@pytest.mark.anyio
async def test_validate_key_unknown_provider_no_http_call() -> None:
    with patch("agt.tools.key_validator.httpx.AsyncClient") as mock_cls:
        valid, error = await validate_key("unknown_provider", "some-key")

    assert valid is False
    assert error == "unknown_provider"
    mock_cls.assert_not_called()


@pytest.mark.anyio
async def test_validate_key_ncbi_key_sent_as_param() -> None:
    """NCBI key should be sent as query param, not a header."""
    captured_params: dict[str, object] = {}
    captured_headers: dict[str, object] = {}

    async def _fake_get(url: str, *, params: object = None, headers: object = None) -> MagicMock:
        if isinstance(params, dict):
            captured_params.update(cast(dict[str, object], params))
        if isinstance(headers, dict):
            captured_headers.update(cast(dict[str, object], headers))
        return _mock_response(_HTTP_OK)

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = _fake_get

    with patch("agt.tools.key_validator.httpx.AsyncClient", return_value=mock_client):
        valid, error = await validate_key("ncbi", "ncbi-key-123")

    assert valid is True
    assert error is None
    assert captured_params.get("api_key") == "ncbi-key-123"
    assert "x-api-key" not in captured_headers


def test_known_providers_is_frozenset_with_all_expected_providers() -> None:
    assert isinstance(KNOWN_PROVIDERS, frozenset)
    expected = {"semantic_scholar", "ncbi", "core", "serpapi", "dimensions"}
    assert expected == KNOWN_PROVIDERS
