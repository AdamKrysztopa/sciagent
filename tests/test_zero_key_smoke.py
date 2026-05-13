"""Zero-key smoke test: verify baseline providers are enabled with no API keys."""

from __future__ import annotations

import pytest

from agt.config import Settings
from agt.tools.query_constraints import SearchConstraintSpec
from agt.tools.search_papers import _build_retrieval_registry  # pyright: ignore[reportPrivateUsage]

_SIX_KEYLESS_PROVIDERS: frozenset[str] = frozenset({
    "openalex",
    "crossref",
    "arxiv",
    "europe_pmc",
    "pubmed",
    "semantic_scholar",
})


@pytest.mark.live_api
def test_six_baseline_providers_enabled_with_no_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    """All six keyless providers must have skip_reason=None when no keys are set."""
    for name in (
        "AGT_CORE_API_KEY",
        "CORE_API_KEY",
        "AGT_DIMENSIONS_KEY",
        "DIMENSIONS_KEY",
        "AGT_SERPAPI_KEY",
        "SERPAPI_KEY",
    ):
        monkeypatch.delenv(name, raising=False)

    settings = Settings(_env_file=None)  # pyright: ignore[reportCallIssue]
    constraints = SearchConstraintSpec(raw_query="test")
    registry = _build_retrieval_registry("test", 10, constraints, settings, None)

    enabled = {r.name for r in registry if r.skip_reason is None}
    missing = _SIX_KEYLESS_PROVIDERS - enabled
    assert not missing, f"Expected these providers to be enabled with no keys: {missing}"
