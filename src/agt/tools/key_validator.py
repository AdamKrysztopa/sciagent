"""Provider API key validation functions.

Each validator makes a minimal test call to the provider's API.
Keys MUST NOT be logged or included in any exception message.

SECURITY: Validate provider name against KNOWN_PROVIDERS allowlist
before making any external call to prevent SSRF.
"""

from __future__ import annotations

import httpx

_HTTP_OK = 200
_HTTP_UNAUTHORIZED = 401
_HTTP_FORBIDDEN = 403

KNOWN_PROVIDERS: frozenset[str] = frozenset({
    "semantic_scholar",
    "ncbi",
    "core",
    "serpapi",
    "dimensions",
})

# Minimal test endpoints for each provider (low-cost, authenticated)
_TEST_ENDPOINTS: dict[str, str] = {
    "semantic_scholar": "https://api.semanticscholar.org/graph/v1/paper/search",
    "ncbi": "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
    "core": "https://api.core.ac.uk/v3/search/works",
    "serpapi": "https://serpapi.com/account",
    "dimensions": "https://metrics-api.dimensions.ai/ping",
}

_TEST_PARAMS: dict[str, dict[str, str]] = {
    "semantic_scholar": {"query": "test", "fields": "paperId", "limit": "1"},
    "ncbi": {"db": "pubmed", "term": "test", "retmax": "1"},
    "core": {"q": "test", "limit": "1"},
    "serpapi": {},
    "dimensions": {},
}

# Providers that send the key in a request header
_KEY_HEADER: dict[str, str] = {
    "semantic_scholar": "x-api-key",
    "core": "Authorization",  # value: "Bearer {key}"
    "dimensions": "Authorization",
}

# Providers that send the key as a query parameter
_KEY_PARAM: dict[str, str] = {
    "ncbi": "api_key",
    "serpapi": "api_key",
}


async def validate_key(provider: str, api_key: str) -> tuple[bool, str | None]:
    """Validate a provider API key with a minimal test call.

    Parameters
    ----------
    provider:
        Provider name. MUST be in KNOWN_PROVIDERS — caller must verify first.
    api_key:
        The key to validate. MUST NOT be logged or included in error strings.

    Returns
    -------
    (valid, error_reason_or_None)
        error_reason is a generic message — never includes the key value.
    """
    # Belt-and-suspenders: never call unknown providers even if caller forgot
    if provider not in KNOWN_PROVIDERS:
        return False, "unknown_provider"

    endpoint = _TEST_ENDPOINTS[provider]
    params: dict[str, str] = dict(_TEST_PARAMS.get(provider, {}))
    headers: dict[str, str] = {}

    if provider in _KEY_HEADER:
        header_name = _KEY_HEADER[provider]
        if header_name == "Authorization":
            headers[header_name] = f"Bearer {api_key}"
        else:
            headers[header_name] = api_key
    elif provider in _KEY_PARAM:
        params[_KEY_PARAM[provider]] = api_key

    error_reason: str | None = None
    response: httpx.Response | None = None
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(endpoint, params=params, headers=headers)
    except httpx.TimeoutException:
        error_reason = "provider_timeout"
    except httpx.NetworkError:
        error_reason = "network_error"
    except Exception:  # pragma: no cover
        error_reason = "connection_error"

    if error_reason is not None:
        return False, error_reason
    assert response is not None
    if response.status_code == _HTTP_OK:
        return True, None
    if response.status_code in (_HTTP_UNAUTHORIZED, _HTTP_FORBIDDEN):
        return False, "invalid_key"
    return False, f"provider_returned_{response.status_code}"
