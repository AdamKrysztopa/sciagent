"""Thread-aware rate-limit and workflow cost guardrails."""

from __future__ import annotations

import asyncio
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field

from agt.config import Settings, get_settings

_thread_id_context: ContextVar[str] = ContextVar("agt_thread_id", default="global")


@dataclass(slots=True)
class _GuardrailsRegistry:
    lock: threading.Lock = field(default_factory=threading.Lock)
    instance: Guardrails | None = None
    signature: (
        tuple[int, int, int, int, int, int, int, int, int, int, int, int, int, float] | None
    ) = None


_registry = _GuardrailsRegistry()


class RateLimitExceededError(RuntimeError):
    """Raised when token bucket cannot serve a request."""


class WorkflowCostExceededError(RuntimeError):
    """Raised when workflow cost exceeds configured budget."""


@dataclass(slots=True)
class TokenBucket:
    """Simple token bucket with refill based on elapsed monotonic time."""

    rate_per_minute: int
    capacity: int
    _tokens: float
    _last_refill_s: float

    @classmethod
    def create(cls, rate_per_minute: int) -> TokenBucket:
        capacity = max(1, rate_per_minute)
        return cls(
            rate_per_minute=rate_per_minute,
            capacity=capacity,
            _tokens=float(capacity),
            _last_refill_s=time.monotonic(),
        )

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = max(0.0, now - self._last_refill_s)
        refill_rate_per_second = self.rate_per_minute / 60.0
        self._tokens = min(self.capacity, self._tokens + elapsed * refill_rate_per_second)
        self._last_refill_s = now

    def consume(self, amount: float = 1.0) -> bool:
        self._refill()
        if self._tokens < amount:
            return False
        self._tokens -= amount
        return True


@dataclass(slots=True)
class Guardrails:
    """In-memory guardrail registry keyed by service and thread_id."""

    semantic_scholar_rate_per_minute: int
    openalex_rate_per_minute: int = 100
    crossref_rate_per_minute: int = 80
    pubmed_rate_per_minute: int = 100
    europe_pmc_rate_per_minute: int = 100
    core_rate_per_minute: int = 60
    arxiv_rate_per_minute: int = 20
    opencitations_rate_per_minute: int = 60
    base_rate_per_minute: int = 40
    dimensions_rate_per_minute: int = 40
    google_scholar_rate_per_minute: int = 20
    zotero_rate_per_minute: int = 60
    llm_rate_per_minute: int = 120
    workflow_max_cost_usd: float = 0.5
    _buckets: dict[tuple[str, str], TokenBucket] = field(init=False)
    _cost_by_thread: dict[str, float] = field(init=False)
    _lock: threading.Lock = field(init=False)

    def __post_init__(self) -> None:
        self._buckets: dict[tuple[str, str], TokenBucket] = {}
        self._cost_by_thread: dict[str, float] = {}
        self._lock = threading.Lock()

    def _service_rate(self, service: str) -> int:
        rates = {
            "semantic_scholar": self.semantic_scholar_rate_per_minute,
            "openalex": self.openalex_rate_per_minute,
            "crossref": self.crossref_rate_per_minute,
            "pubmed": self.pubmed_rate_per_minute,
            "europe_pmc": self.europe_pmc_rate_per_minute,
            "core": self.core_rate_per_minute,
            "arxiv": self.arxiv_rate_per_minute,
            "opencitations": self.opencitations_rate_per_minute,
            "base": self.base_rate_per_minute,
            "dimensions": self.dimensions_rate_per_minute,
            "google_scholar": self.google_scholar_rate_per_minute,
            "zotero": self.zotero_rate_per_minute,
        }
        return rates.get(service, self.llm_rate_per_minute)

    def acquire(self, service: str, thread_id: str) -> None:
        with self._lock:
            key = (service, thread_id)
            bucket = self._buckets.get(key)
            if bucket is None:
                bucket = TokenBucket.create(self._service_rate(service))
                self._buckets[key] = bucket
            if not bucket.consume():
                raise RateLimitExceededError(
                    f"Rate limit reached for {service}. Please try again later."
                )

    def record_cost(self, thread_id: str, amount_usd: float) -> None:
        with self._lock:
            spent = self._cost_by_thread.get(thread_id, 0.0) + max(0.0, amount_usd)
            if spent > self.workflow_max_cost_usd:
                raise WorkflowCostExceededError(
                    "Workflow cost guard reached. Please narrow your query and try again later."
                )
            self._cost_by_thread[thread_id] = spent

    async def wait_for_token(
        self,
        service: str,
        thread_id: str,
        timeout_seconds: float,
    ) -> bool:
        """Wait for a token to become available, up to timeout_seconds."""

        deadline = time.monotonic() + max(0.0, timeout_seconds)
        while True:
            with self._lock:
                key = (service, thread_id)
                bucket = self._buckets.get(key)
                if bucket is None:
                    bucket = TokenBucket.create(self._service_rate(service))
                    self._buckets[key] = bucket
                if bucket.consume():
                    return True

            if time.monotonic() >= deadline:
                return False

            await asyncio.sleep(0.05)


def _guardrail_signature(
    settings: Settings,
) -> tuple[int, int, int, int, int, int, int, int, int, int, int, int, int, float]:
    return (
        settings.semantic_scholar_rate_limit_per_minute,
        settings.openalex_rate_limit_per_minute,
        settings.crossref_rate_limit_per_minute,
        settings.pubmed_rate_limit_per_minute,
        settings.europe_pmc_rate_limit_per_minute,
        settings.core_rate_limit_per_minute,
        settings.arxiv_rate_limit_per_minute,
        settings.opencitations_rate_limit_per_minute,
        settings.base_rate_limit_per_minute,
        settings.dimensions_rate_limit_per_minute,
        settings.google_scholar_rate_limit_per_minute,
        settings.zotero_rate_limit_per_minute,
        settings.llm_rate_limit_per_minute,
        settings.workflow_max_cost_usd,
    )


def configure_guardrails(settings: Settings) -> Guardrails:
    """Configure singleton guardrails from validated settings."""

    signature = _guardrail_signature(settings)
    with _registry.lock:
        if _registry.instance is None or _registry.signature != signature:
            _registry.instance = Guardrails(
                semantic_scholar_rate_per_minute=settings.semantic_scholar_rate_limit_per_minute,
                openalex_rate_per_minute=settings.openalex_rate_limit_per_minute,
                crossref_rate_per_minute=settings.crossref_rate_limit_per_minute,
                pubmed_rate_per_minute=settings.pubmed_rate_limit_per_minute,
                europe_pmc_rate_per_minute=settings.europe_pmc_rate_limit_per_minute,
                core_rate_per_minute=settings.core_rate_limit_per_minute,
                arxiv_rate_per_minute=settings.arxiv_rate_limit_per_minute,
                opencitations_rate_per_minute=settings.opencitations_rate_limit_per_minute,
                base_rate_per_minute=settings.base_rate_limit_per_minute,
                dimensions_rate_per_minute=settings.dimensions_rate_limit_per_minute,
                google_scholar_rate_per_minute=settings.google_scholar_rate_limit_per_minute,
                zotero_rate_per_minute=settings.zotero_rate_limit_per_minute,
                llm_rate_per_minute=settings.llm_rate_limit_per_minute,
                workflow_max_cost_usd=settings.workflow_max_cost_usd,
            )
            _registry.signature = signature
    return _registry.instance


def get_guardrails() -> Guardrails:
    """Get guardrails singleton, bootstrapping from current settings if needed."""

    if _registry.instance is not None:
        return _registry.instance

    settings = get_settings()
    return configure_guardrails(settings)


def current_thread_id() -> str:
    """Return current workflow thread identifier from context."""

    return _thread_id_context.get()


@contextmanager
def thread_context(thread_id: str) -> Iterator[None]:
    """Set current workflow thread_id for guardrail-aware calls."""

    token = _thread_id_context.set(thread_id)
    try:
        yield
    finally:
        _thread_id_context.reset(token)
