from __future__ import annotations

import httpx

from agt.config import Settings
from agt.zotero.preflight import run_zotero_preflight


def _settings() -> Settings:
    return Settings.model_validate({
        "AGT_XAI_API_KEY": "xai-secret",
        "AGT_ZOTERO_API_KEY": "zot-secret",
        "AGT_ZOTERO_LIBRARY_ID": "12345",
        "AGT_ZOTERO_LIBRARY_TYPE": "user",
    })


# Real Zotero /keys/current response shape: {"access": {"user": {"write": true}, ...}}
_KEY_WITH_WRITE = {"access": {"user": {"library": True, "write": True, "files": True}}}
_KEY_NO_WRITE = {"access": {"user": {"library": True, "write": False}}}


def test_preflight_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/keys/current":
            return httpx.Response(200, json=_KEY_WITH_WRITE)
        if request.url.path.startswith("/users/12345/collections"):
            return httpx.Response(200, json=[])
        return httpx.Response(404)

    client = httpx.Client(base_url="https://api.zotero.org", transport=httpx.MockTransport(handler))
    result = run_zotero_preflight(_settings(), client=client)
    assert result.ok is True
    assert result.can_read is True
    assert result.can_write is True


def test_preflight_detects_missing_write_permission() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/keys/current":
            return httpx.Response(200, json=_KEY_NO_WRITE)
        if request.url.path.startswith("/users/12345/collections"):
            return httpx.Response(200, json=[])
        return httpx.Response(404)

    client = httpx.Client(base_url="https://api.zotero.org", transport=httpx.MockTransport(handler))
    result = run_zotero_preflight(_settings(), client=client)
    assert result.ok is False
    assert result.can_read is True
    assert result.can_write is False
    assert "lacks write permission" in result.message


def test_preflight_detects_library_access_problem() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/keys/current":
            return httpx.Response(200, json=_KEY_WITH_WRITE)
        if request.url.path.startswith("/users/12345/collections"):
            return httpx.Response(403)
        return httpx.Response(404)

    client = httpx.Client(base_url="https://api.zotero.org", transport=httpx.MockTransport(handler))
    result = run_zotero_preflight(_settings(), client=client)
    assert result.ok is False
    assert result.can_read is False
    assert "Unable to access target Zotero library" in result.message
