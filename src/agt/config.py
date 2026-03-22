"""Typed runtime settings and log redaction helpers."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="AGT_", extra="ignore")

    xai_api_key: SecretStr = Field(..., description="xAI API key")
    zotero_api_key: SecretStr = Field(..., description="Zotero API key")
    zotero_library_id: str = Field(..., description="Zotero library id")
    zotero_library_type: str = Field(default="user", pattern="^(user|group)$")
    semantic_scholar_api_key: SecretStr | None = None
    model_name: str = "grok-4"
    timeout_seconds: int = 30
    retries: int = 3
    log_level: str = "INFO"


@dataclass(slots=True)
class RedactionFilter(logging.Filter):
    """Best-effort redaction for common secret patterns in log messages."""

    replacements: tuple[str, ...] = (
        "api_key",
        "authorization",
        "bearer",
        "token",
        "secret",
    )

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        lowered = message.lower()
        if any(secret in lowered for secret in self.replacements):
            record.msg = "[REDACTED SENSITIVE LOG MESSAGE]"
            record.args = ()
        return True


def get_settings() -> Settings:
    """Load validated settings, failing fast on missing required config."""

    return Settings()  # pyright: ignore[reportCallIssue]
