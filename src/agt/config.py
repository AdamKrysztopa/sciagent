"""Typed runtime settings, startup validation, and redacted structured logging."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal, cast

import structlog
from pydantic import AliasChoices, BaseModel, Field, SecretStr, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LLMProviderName = Literal["xai", "openai", "anthropic", "groq"]
LibraryType = Literal["user", "group"]
RuntimeEnvironment = Literal["local", "staging", "production"]


class RuntimeConfig(BaseModel):
    """Runtime tuning parameters used by provider adapters."""

    provider: LLMProviderName = "xai"
    model_name: str = "grok-4"
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    retries: int = Field(default=3, ge=0, le=10)
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)


def _empty_env_overrides() -> dict[RuntimeEnvironment, RuntimeConfig]:
    return {}


class Settings(BaseSettings):
    """Application settings loaded from environment variables with strict validation."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="AGT_", extra="forbid")

    xai_api_key: SecretStr = Field(
        ...,
        validation_alias=AliasChoices("AGT_XAI_API_KEY", "XAI_API_KEY"),
        description="xAI API key",
    )
    zotero_api_key: SecretStr = Field(
        ...,
        validation_alias=AliasChoices("AGT_ZOTERO_API_KEY", "ZOTERO_API_KEY"),
        description="Zotero API key",
    )
    zotero_library_id: str = Field(
        ...,
        min_length=1,
        validation_alias=AliasChoices("AGT_ZOTERO_LIBRARY_ID", "ZOTERO_LIBRARY_ID"),
        description="Zotero library id",
    )
    zotero_library_type: LibraryType = Field(
        default="user",
        validation_alias=AliasChoices("AGT_ZOTERO_LIBRARY_TYPE", "ZOTERO_LIBRARY_TYPE"),
    )
    semantic_scholar_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("AGT_SEMANTIC_SCHOLAR_API_KEY", "SEMANTIC_SCHOLAR_API_KEY"),
    )
    ncbi_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("AGT_NCBI_API_KEY", "NCBI_API_KEY"),
    )
    core_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("AGT_CORE_API_KEY", "CORE_API_KEY"),
    )
    serpapi_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("AGT_SERPAPI_KEY", "SERPAPI_KEY"),
    )
    dimensions_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("AGT_DIMENSIONS_KEY", "DIMENSIONS_KEY"),
    )
    openai_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("AGT_OPENAI_API_KEY", "OPENAI_API_KEY"),
    )
    anthropic_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("AGT_ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY"),
    )
    groq_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("AGT_GROQ_API_KEY", "GROQ_API_KEY"),
    )

    env: RuntimeEnvironment = Field(
        default="local", validation_alias=AliasChoices("AGT_ENV", "ENV")
    )

    llm_provider: LLMProviderName = Field(
        default="xai",
        validation_alias=AliasChoices("AGT_LLM_PROVIDER", "LLM_PROVIDER"),
    )
    model_name: str = Field(
        default="grok-4", validation_alias=AliasChoices("AGT_MODEL_NAME", "MODEL_NAME")
    )
    timeout_seconds: int = Field(
        default=30,
        ge=1,
        le=300,
        validation_alias=AliasChoices("AGT_TIMEOUT_SECONDS", "TIMEOUT_SECONDS"),
    )
    retries: int = Field(
        default=3, ge=0, le=10, validation_alias=AliasChoices("AGT_RETRIES", "RETRIES")
    )
    temperature: float = Field(
        default=0.2,
        ge=0.0,
        le=2.0,
        validation_alias=AliasChoices("AGT_TEMPERATURE", "TEMPERATURE"),
    )
    semantic_scholar_timeout_seconds: int = Field(
        default=15,
        ge=1,
        le=120,
        validation_alias=AliasChoices(
            "AGT_SEMANTIC_SCHOLAR_TIMEOUT_SECONDS", "SEMANTIC_SCHOLAR_TIMEOUT_SECONDS"
        ),
    )
    semantic_scholar_retries: int = Field(
        default=2,
        ge=0,
        le=10,
        validation_alias=AliasChoices("AGT_SEMANTIC_SCHOLAR_RETRIES", "SEMANTIC_SCHOLAR_RETRIES"),
    )
    semantic_scholar_limit: int = Field(
        default=10,
        ge=1,
        le=100,
        validation_alias=AliasChoices("AGT_SEMANTIC_SCHOLAR_LIMIT", "SEMANTIC_SCHOLAR_LIMIT"),
    )
    summarization_max_sentences: int = Field(
        default=4,
        ge=3,
        le=4,
        validation_alias=AliasChoices(
            "AGT_SUMMARIZATION_MAX_SENTENCES", "SUMMARIZATION_MAX_SENTENCES"
        ),
    )
    summarization_use_llm: bool = Field(
        default=True,
        validation_alias=AliasChoices("AGT_SUMMARIZATION_USE_LLM", "SUMMARIZATION_USE_LLM"),
    )
    semantic_scholar_rate_limit_per_minute: int = Field(
        default=100,
        ge=1,
        validation_alias=AliasChoices(
            "AGT_SEMANTIC_SCHOLAR_RATE_LIMIT_PER_MINUTE", "SEMANTIC_SCHOLAR_RATE_LIMIT_PER_MINUTE"
        ),
    )
    openalex_rate_limit_per_minute: int = Field(
        default=100,
        ge=1,
        validation_alias=AliasChoices(
            "AGT_OPENALEX_RATE_LIMIT_PER_MINUTE", "OPENALEX_RATE_LIMIT_PER_MINUTE"
        ),
    )
    crossref_rate_limit_per_minute: int = Field(
        default=80,
        ge=1,
        validation_alias=AliasChoices(
            "AGT_CROSSREF_RATE_LIMIT_PER_MINUTE", "CROSSREF_RATE_LIMIT_PER_MINUTE"
        ),
    )
    pubmed_rate_limit_per_minute: int = Field(
        default=100,
        ge=1,
        validation_alias=AliasChoices(
            "AGT_PUBMED_RATE_LIMIT_PER_MINUTE", "PUBMED_RATE_LIMIT_PER_MINUTE"
        ),
    )
    europe_pmc_rate_limit_per_minute: int = Field(
        default=100,
        ge=1,
        validation_alias=AliasChoices(
            "AGT_EUROPE_PMC_RATE_LIMIT_PER_MINUTE", "EUROPE_PMC_RATE_LIMIT_PER_MINUTE"
        ),
    )
    core_rate_limit_per_minute: int = Field(
        default=60,
        ge=1,
        validation_alias=AliasChoices(
            "AGT_CORE_RATE_LIMIT_PER_MINUTE", "CORE_RATE_LIMIT_PER_MINUTE"
        ),
    )
    arxiv_rate_limit_per_minute: int = Field(
        default=20,
        ge=1,
        validation_alias=AliasChoices(
            "AGT_ARXIV_RATE_LIMIT_PER_MINUTE", "ARXIV_RATE_LIMIT_PER_MINUTE"
        ),
    )
    opencitations_rate_limit_per_minute: int = Field(
        default=60,
        ge=1,
        validation_alias=AliasChoices(
            "AGT_OPENCITATIONS_RATE_LIMIT_PER_MINUTE", "OPENCITATIONS_RATE_LIMIT_PER_MINUTE"
        ),
    )
    base_rate_limit_per_minute: int = Field(
        default=40,
        ge=1,
        validation_alias=AliasChoices(
            "AGT_BASE_RATE_LIMIT_PER_MINUTE", "BASE_RATE_LIMIT_PER_MINUTE"
        ),
    )
    dimensions_rate_limit_per_minute: int = Field(
        default=40,
        ge=1,
        validation_alias=AliasChoices(
            "AGT_DIMENSIONS_RATE_LIMIT_PER_MINUTE", "DIMENSIONS_RATE_LIMIT_PER_MINUTE"
        ),
    )
    google_scholar_rate_limit_per_minute: int = Field(
        default=20,
        ge=1,
        validation_alias=AliasChoices(
            "AGT_GOOGLE_SCHOLAR_RATE_LIMIT_PER_MINUTE", "GOOGLE_SCHOLAR_RATE_LIMIT_PER_MINUTE"
        ),
    )
    search_max_pages: int = Field(
        default=1,
        ge=1,
        le=5,
        validation_alias=AliasChoices("AGT_SEARCH_MAX_PAGES", "SEARCH_MAX_PAGES"),
    )
    citation_threshold_most_cited: int = Field(
        default=10,
        ge=0,
        validation_alias=AliasChoices(
            "AGT_CITATION_THRESHOLD_MOST_CITED", "CITATION_THRESHOLD_MOST_CITED"
        ),
    )
    citation_threshold_game_changers: int = Field(
        default=20,
        ge=0,
        validation_alias=AliasChoices(
            "AGT_CITATION_THRESHOLD_GAME_CHANGERS", "CITATION_THRESHOLD_GAME_CHANGERS"
        ),
    )
    citation_threshold_trending: int = Field(
        default=5,
        ge=0,
        validation_alias=AliasChoices(
            "AGT_CITATION_THRESHOLD_TRENDING", "CITATION_THRESHOLD_TRENDING"
        ),
    )
    use_keybert: bool = Field(
        default=False,
        validation_alias=AliasChoices("AGT_USE_KEYBERT", "USE_KEYBERT"),
    )
    use_spell_check: bool = Field(
        default=False,
        validation_alias=AliasChoices("AGT_USE_SPELL_CHECK", "USE_SPELL_CHECK"),
    )
    use_reranker: bool = Field(
        default=False,
        validation_alias=AliasChoices("AGT_USE_RERANKER", "USE_RERANKER"),
    )
    enable_fallback_retrieval: bool = Field(
        default=False,
        validation_alias=AliasChoices("AGT_ENABLE_FALLBACK_RETRIEVAL", "ENABLE_FALLBACK_RETRIEVAL"),
    )
    zotero_rate_limit_per_minute: int = Field(
        default=60,
        ge=1,
        validation_alias=AliasChoices(
            "AGT_ZOTERO_RATE_LIMIT_PER_MINUTE", "ZOTERO_RATE_LIMIT_PER_MINUTE"
        ),
    )
    llm_rate_limit_per_minute: int = Field(
        default=120,
        ge=1,
        validation_alias=AliasChoices("AGT_LLM_RATE_LIMIT_PER_MINUTE", "LLM_RATE_LIMIT_PER_MINUTE"),
    )
    workflow_max_cost_usd: float = Field(
        default=0.5,
        ge=0.01,
        validation_alias=AliasChoices("AGT_WORKFLOW_MAX_COST_USD", "WORKFLOW_MAX_COST_USD"),
    )
    xai_input_cost_per_1k_tokens_usd: float = Field(
        default=0.005,
        ge=0.0,
        validation_alias=AliasChoices(
            "AGT_XAI_INPUT_COST_PER_1K_TOKENS_USD", "XAI_INPUT_COST_PER_1K_TOKENS_USD"
        ),
    )
    xai_output_cost_per_1k_tokens_usd: float = Field(
        default=0.015,
        ge=0.0,
        validation_alias=AliasChoices(
            "AGT_XAI_OUTPUT_COST_PER_1K_TOKENS_USD", "XAI_OUTPUT_COST_PER_1K_TOKENS_USD"
        ),
    )
    env_overrides: dict[RuntimeEnvironment, RuntimeConfig] = Field(
        default_factory=_empty_env_overrides,
        validation_alias=AliasChoices("AGT_ENV_OVERRIDES", "ENV_OVERRIDES"),
        description="JSON mapping of env name to runtime overrides.",
    )
    log_level: str = Field(
        default="INFO", validation_alias=AliasChoices("AGT_LOG_LEVEL", "LOG_LEVEL")
    )

    @field_validator("env_overrides", mode="before")
    @classmethod
    def _decode_env_overrides(
        cls, value: object
    ) -> dict[RuntimeEnvironment, RuntimeConfig] | object:
        if isinstance(value, str):
            parsed: object = json.loads(value)
            if not isinstance(parsed, dict):
                raise ValueError("AGT_ENV_OVERRIDES must be a JSON object")
            return cast(dict[RuntimeEnvironment, RuntimeConfig], parsed)
        return value

    @property
    def runtime(self) -> RuntimeConfig:
        base = RuntimeConfig(
            provider=self.llm_provider,
            model_name=self.model_name,
            timeout_seconds=self.timeout_seconds,
            retries=self.retries,
            temperature=self.temperature,
        )
        override: RuntimeConfig | None = self.env_overrides.get(self.env)
        if override is None:
            return base
        return base.model_copy(update=override.model_dump(exclude_unset=True))


def redact_value(value: object) -> object:
    """Recursively redact sensitive values in structured payloads."""

    if isinstance(value, dict):
        mapping = cast(dict[object, object], value)
        redacted: dict[str, object] = {}
        for key_obj, inner_obj in mapping.items():
            key = str(key_obj)
            lowered = key.lower()
            if any(
                token in lowered
                for token in ("key", "token", "secret", "authorization", "password")
            ):
                redacted[key] = "[REDACTED]"
            else:
                redacted[key] = redact_value(inner_obj)
        return redacted
    if isinstance(value, list):
        items = cast(list[object], value)
        return [redact_value(item) for item in items]
    if isinstance(value, SecretStr):
        return "[REDACTED]"
    if isinstance(value, str):
        lowered = value.lower()
        if any(token in lowered for token in ("bearer ", "api_key", "token", "secret")):
            return "[REDACTED]"
    return value


def _redaction_processor(
    _: structlog.types.WrappedLogger, __: str, event_dict: structlog.types.EventDict
) -> structlog.types.EventDict:
    return cast(structlog.types.EventDict, redact_value(event_dict))


@dataclass(slots=True)
class RedactionFilter(logging.Filter):
    """Best-effort redaction for common secret patterns in plain log messages."""

    replacements: tuple[str, ...] = (
        "api_key",
        "authorization",
        "bearer",
        "token",
        "secret",
        "password",
    )

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        lowered = message.lower()
        if any(secret in lowered for secret in self.replacements):
            record.msg = "[REDACTED SENSITIVE LOG MESSAGE]"
            record.args = ()
        return True


@lru_cache(maxsize=1)
def configure_logging(level: str = "INFO") -> None:
    """Configure structured logging and redaction once per process."""

    root_logger = logging.getLogger()
    root_logger.setLevel(level.upper())
    root_logger.addFilter(RedactionFilter())
    if not root_logger.handlers:
        handler = logging.StreamHandler()
        handler.setLevel(level.upper())
        handler.addFilter(RedactionFilter())
        root_logger.addHandler(handler)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            _redaction_processor,
            structlog.processors.add_log_level,
            structlog.processors.EventRenamer("message"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(root_logger.level),
    )


def _format_settings_validation_error(exc: ValidationError) -> str:
    missing: list[str] = []
    invalid: list[str] = []
    for err in exc.errors():
        loc = ".".join(str(part) for part in err.get("loc", []))
        if err.get("type") == "missing":
            missing.append(loc)
        else:
            invalid.append(f"{loc}: {err.get('msg', 'invalid value')}")

    messages: list[str] = []
    if missing:
        messages.append("Missing required settings: " + ", ".join(sorted(set(missing))))
    if invalid:
        messages.append("Invalid settings: " + "; ".join(invalid))
    if not messages:
        messages.append(str(exc))
    return " | ".join(messages)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load validated settings and fail fast with actionable startup errors."""

    try:
        return Settings()  # pyright: ignore[reportCallIssue]
    except ValidationError as exc:
        raise RuntimeError(_format_settings_validation_error(exc)) from exc
