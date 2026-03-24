"""OpenCitations COCI client for DOI citation enrichment."""

# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnknownMemberType=false

from __future__ import annotations

from typing import Any, cast
from urllib.parse import quote

import httpx
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential


class OpenCitationsResponseError(RuntimeError):
    """Raised when OpenCitations payload is malformed."""


class OpenCitationsClient:
    """Small bounded client for COCI citation-count endpoint."""

    def __init__(
        self,
        *,
        timeout_seconds: int,
        retries: int,
        base_url: str = "https://opencitations.net/index/coci/api/v1",
    ) -> None:
        self._timeout_seconds = timeout_seconds
        self._retries = retries
        self._base_url = base_url.rstrip("/")

    async def citation_count(self, doi: str) -> int | None:
        if not doi.strip():
            return None

        encoded = quote(doi.strip(), safe="")
        payload = await self._request_json(path=f"/citation-count/{encoded}")
        if not isinstance(payload, list):
            raise OpenCitationsResponseError("OpenCitations payload must be a list")
        if not payload:
            return None

        first = payload[0]
        if not isinstance(first, dict):
            raise OpenCitationsResponseError("OpenCitations list item must be an object")
        mapping = cast(dict[str, Any], first)

        value = mapping.get("count")
        if isinstance(value, str) and value.isdigit():
            return int(value)
        if isinstance(value, int):
            return max(0, value)
        return None

    async def _request_json(self, *, path: str) -> object:
        url = f"{self._base_url}{path}"
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(self._retries + 1),
            wait=wait_exponential(multiplier=1, min=1, max=8),
            retry=retry_if_exception_type((
                httpx.TimeoutException,
                httpx.NetworkError,
                httpx.HTTPStatusError,
            )),
            reraise=True,
        ):
            with attempt:
                async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                    response = await client.get(url)
                    response.raise_for_status()
                    return response.json()

        raise OpenCitationsResponseError("OpenCitations request failed")
