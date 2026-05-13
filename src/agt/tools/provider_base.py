"""Base class and protocol for SciAgent search providers.

WARNING: Do not confuse SearchProviderBase (this module) with
BaseSearchClient (src/agt/tools/base_search.py — the Bielefeld Academic
Search Engine (BASE SRU) provider).

``SearchProviderProtocol`` — runtime-checkable structural type for any object
that behaves as a search provider. Distinct from ``LLMProvider`` in
``agt.providers.protocol`` — this describes academic search sources, not
language model backends.

``SearchProviderBase`` — convenience base class that wires health bookkeeping,
httpx client lifecycle, and error wrapping. Subclasses must:
1. Set ``capabilities_`` at class level.
2. Implement ``_search_impl``.
"""

from __future__ import annotations

import time
from typing import ClassVar, Protocol, runtime_checkable

import httpx

from agt.models import NormalizedPaper
from agt.tools.capabilities import ProviderHealth, ProviderStatus, SearchProviderCapabilities

_USER_AGENT_BASE = "SciAgent/0.1 (https://github.com/AdamKrysztopa/sciagent)"


@runtime_checkable
class SearchProviderProtocol(Protocol):
    """Structural protocol for SciAgent search providers.

    Any class that implements ``capabilities``, ``health``, and ``search`` with
    the correct signatures satisfies this protocol. Distinct from
    ``LLMProvider`` — this describes academic search sources, not LLM backends.
    """

    def capabilities(self) -> SearchProviderCapabilities: ...

    def health(self) -> ProviderHealth: ...

    async def search(
        self,
        query: str,
        *,
        limit: int = 25,
        author: str | None = None,
        year_from: int | None = None,
        year_to: int | None = None,
    ) -> list[NormalizedPaper]: ...


class SearchProviderBase:
    """Convenience base class for SciAgent search providers.

    Subclasses must set ``capabilities_`` at class level and implement
    ``_search_impl``. This class provides:
    - httpx.AsyncClient construction with correct User-Agent and Accept headers.
    - Health bookkeeping (status, timestamps, consecutive failure count).
    - Error wrapping: ``_record_success`` / ``_record_failure`` called around
      every ``_search_impl`` invocation.

    WARNING: Do not confuse this with BaseSearchClient
    (src/agt/tools/base_search.py — the BASE SRU provider).
    """

    capabilities_: ClassVar[SearchProviderCapabilities]

    def __init__(self, *, mailto: str | None = None, timeout: float = 15.0) -> None:
        self._mailto = mailto
        self._timeout = timeout
        self._health = ProviderHealth()
        self._client = httpx.AsyncClient(
            headers={
                "User-Agent": self._user_agent(),
                "Accept": "application/json",
            },
            timeout=timeout,
        )

    def _user_agent(self) -> str:
        """Return the User-Agent string, appending mailto if configured."""
        ua = _USER_AGENT_BASE
        if self._mailto:
            ua += f" mailto:{self._mailto}"
        return ua

    def capabilities(self) -> SearchProviderCapabilities:
        """Return the static capability declaration for this provider."""
        return self.capabilities_

    def health(self) -> ProviderHealth:
        """Return the current mutable health state."""
        return self._health

    async def search(
        self,
        query: str,
        *,
        limit: int = 25,
        author: str | None = None,
        year_from: int | None = None,
        year_to: int | None = None,
    ) -> list[NormalizedPaper]:
        """Run a search, updating health state on success or failure."""
        try:
            result = await self._search_impl(
                query,
                limit=limit,
                author=author,
                year_from=year_from,
                year_to=year_to,
            )
        except Exception as exc:
            self._record_failure(exc)
            raise
        self._record_success()
        return result

    def _record_success(self) -> None:
        """Mark the provider as healthy after a successful search."""
        self._health.last_ok_at = time.time()
        self._health.consecutive_failures = 0
        self._health.status = ProviderStatus.AVAILABLE
        self._health.reason = ""

    def _record_failure(self, exc: Exception) -> None:
        """Record a failed search attempt in the health state."""
        self._health.last_error_at = time.time()
        self._health.consecutive_failures += 1
        self._health.status = ProviderStatus.FAILED
        self._health.reason = str(exc)

    async def _search_impl(
        self,
        query: str,
        *,
        limit: int = 25,
        author: str | None = None,
        year_from: int | None = None,
        year_to: int | None = None,
    ) -> list[NormalizedPaper]:
        """Provider-specific search implementation. Must be overridden."""
        raise NotImplementedError

    async def aclose(self) -> None:
        """Close the underlying httpx client."""
        await self._client.aclose()
