import logging
from typing import cast

import pytest

from agt.config import RedactionFilter, RuntimeConfig, Settings, get_settings, redact_value


def _settings_from(data: dict[str, object]) -> Settings:
    return Settings.model_validate(data)


def _clear_required_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in (
        "AGT_XAI_API_KEY",
        "XAI_API_KEY",
        "AGT_ZOTERO_API_KEY",
        "ZOTERO_API_KEY",
        "AGT_ZOTERO_LIBRARY_ID",
        "ZOTERO_LIBRARY_ID",
    ):
        monkeypatch.delenv(name, raising=False)


def test_redaction_filter_masks_sensitive_text() -> None:
    filt = RedactionFilter()

    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="authorization: Bearer abc",
        args=(),
        exc_info=None,
    )
    assert filt.filter(record) is True
    assert record.msg == "[REDACTED SENSITIVE LOG MESSAGE]"


def test_redact_value_masks_structured_payloads() -> None:
    payload = {
        "authorization": "Bearer abc",
        "nested": {"api_key": "secret", "safe": "ok"},
    }
    redacted = cast(dict[str, object], redact_value(payload))
    nested = cast(dict[str, object], redacted["nested"])
    assert redacted["authorization"] == "[REDACTED]"
    assert nested["api_key"] == "[REDACTED]"
    assert nested["safe"] == "ok"


def test_settings_accept_plain_aliases(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_required_env(monkeypatch)
    settings = _settings_from({
        "XAI_API_KEY": "xai-secret",
        "ZOTERO_API_KEY": "zot-secret",
        "ZOTERO_LIBRARY_ID": "12345",
    })
    assert settings.xai_api_key.get_secret_value() == "xai-secret"
    assert settings.zotero_library_id == "12345"


def test_settings_runtime_uses_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    expected_timeout = 12
    _clear_required_env(monkeypatch)
    settings = _settings_from({
        "AGT_XAI_API_KEY": "xai-secret",
        "AGT_ZOTERO_API_KEY": "zot-secret",
        "AGT_ZOTERO_LIBRARY_ID": "12345",
        "AGT_ENV": "staging",
        "AGT_ENV_OVERRIDES": {
            "staging": {
                "provider": "xai",
                "model_name": "grok-4-fast",
                "timeout_seconds": 12,
                "retries": 1,
                "temperature": 0.0,
            }
        },
    })
    runtime = settings.runtime
    assert isinstance(runtime, RuntimeConfig)
    assert runtime.model_name == "grok-4-fast"
    assert runtime.timeout_seconds == expected_timeout
    assert runtime.retries == 1
    assert runtime.temperature == 0.0


def test_settings_reject_unknown_init_field() -> None:
    with pytest.raises(Exception):
        _settings_from({"unknown_field": "x"})


def test_get_settings_fails_fast_with_actionable_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    get_settings.cache_clear()
    _clear_required_env(monkeypatch)

    with pytest.raises(RuntimeError) as exc:
        get_settings()

    text = str(exc.value)
    assert "Missing required settings" in text
    assert "AGT_ZOTERO_API_KEY" in text or "ZOTERO_API_KEY" in text
