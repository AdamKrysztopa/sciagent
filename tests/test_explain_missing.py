"""Tests for explain_missing.annotate_missing.

Coverage:
1. not_requested_at_depth — field in profile_skipped, attr is None.
2. not_supported_by_any_queried_provider — queried has no support for field.
3. missing_key — capable provider has MISSING_KEY health status.
4. provider_failed — capable provider has FAILED health status.
5. provider_did_not_return — capable provider is healthy but field absent.
6. Present field is NOT annotated (already populated → not in missing_reasons).
7. Already-set reason is NOT overwritten (idempotent second call).
8. queried=[] and no health → all fields get not_supported_by_any_queried_provider.
"""

from __future__ import annotations

from agt.models import NormalizedAuthor, NormalizedPaper
from agt.tools.capabilities import (
    OPENALEX_CAPS,
    FieldSupport,
    ProviderField,
    ProviderHealth,
    ProviderStatus,
    SearchProviderCapabilities,
)
from agt.tools.explain_missing import FIELD_TO_ATTR, annotate_missing

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_F = ProviderField
_S = FieldSupport


def _caps(name: str, fields: dict[ProviderField, FieldSupport]) -> SearchProviderCapabilities:
    """Build a minimal SearchProviderCapabilities for testing."""
    return SearchProviderCapabilities(name=name, fields=fields)


def _health(status: ProviderStatus) -> ProviderHealth:
    return ProviderHealth(status=status)


def _empty_paper() -> NormalizedPaper:
    """Return a NormalizedPaper with all optional fields absent."""
    return NormalizedPaper(title="Test Paper", source="openalex")


# ---------------------------------------------------------------------------
# Reason: not_requested_at_depth
# ---------------------------------------------------------------------------


def test_not_requested_at_depth() -> None:
    """Field in profile_skipped and absent → reason is not_requested_at_depth."""
    paper = _empty_paper()
    caps = _caps("openalex", {_F.REFERENCES: _S.FULL})
    annotate_missing(
        paper,
        queried=[caps],
        health={},
        profile_skipped={_F.REFERENCES},
    )
    assert paper.missing_reasons.get("references") == "not_requested_at_depth"


# ---------------------------------------------------------------------------
# Reason: not_supported_by_any_queried_provider
# ---------------------------------------------------------------------------


def test_not_supported_by_any_queried_provider() -> None:
    """No queried provider supports field → not_supported_by_any_queried_provider."""
    paper = _empty_paper()
    caps = _caps("openalex", {_F.REFERENCES: _S.NONE})
    annotate_missing(paper, queried=[caps], health={})
    assert paper.missing_reasons.get("references") == "not_supported_by_any_queried_provider"


def test_empty_queried_list_all_not_supported() -> None:
    """queried=[] → every missing field gets not_supported_by_any_queried_provider."""
    paper = _empty_paper()
    annotate_missing(paper, queried=[], health={})
    for _, attr in FIELD_TO_ATTR.items():
        if not getattr(paper, attr, None):
            assert paper.missing_reasons.get(attr) == "not_supported_by_any_queried_provider", (
                f"expected not_supported_by_any_queried_provider for {attr}"
            )


# ---------------------------------------------------------------------------
# Reason: missing_key
# ---------------------------------------------------------------------------


def test_missing_key_reason() -> None:
    """All capable providers have MISSING_KEY status → reason is missing_key."""
    paper = _empty_paper()
    caps = _caps("core", {_F.ABSTRACT: _S.FULL})
    health = {"core": _health(ProviderStatus.MISSING_KEY)}
    annotate_missing(paper, queried=[caps], health=health)
    assert paper.missing_reasons.get("abstract") == "missing_key"


def test_missing_key_only_when_all_capable_are_missing_key() -> None:
    """If one capable provider is healthy, missing_key should NOT be reported."""
    paper = _empty_paper()
    caps_core = _caps("core", {_F.ABSTRACT: _S.FULL})
    caps_openalex = _caps("openalex", {_F.ABSTRACT: _S.FULL})
    health = {
        "core": _health(ProviderStatus.MISSING_KEY),
        # openalex has no health entry → treated as not-missing-key
    }
    annotate_missing(paper, queried=[caps_core, caps_openalex], health=health)
    # Should NOT be missing_key since openalex has no health entry (not MISSING_KEY)
    assert paper.missing_reasons.get("abstract") != "missing_key"


# ---------------------------------------------------------------------------
# Reason: provider_failed
# ---------------------------------------------------------------------------


def test_provider_failed_reason() -> None:
    """Capable provider has FAILED status → reason is provider_failed."""
    paper = _empty_paper()
    caps = _caps("europe_pmc", {_F.ABSTRACT: _S.FULL})
    health = {"europe_pmc": _health(ProviderStatus.FAILED)}
    annotate_missing(paper, queried=[caps], health=health)
    assert paper.missing_reasons.get("abstract") == "provider_failed"


def test_rate_limited_provider_reports_provider_failed() -> None:
    """Capable provider with RATE_LIMITED status → reason is provider_failed."""
    paper = _empty_paper()
    caps = _caps("pubmed", {_F.ABSTRACT: _S.FULL})
    health = {"pubmed": _health(ProviderStatus.RATE_LIMITED)}
    annotate_missing(paper, queried=[caps], health=health)
    assert paper.missing_reasons.get("abstract") == "provider_failed"


# ---------------------------------------------------------------------------
# Reason: provider_did_not_return
# ---------------------------------------------------------------------------


def test_provider_did_not_return() -> None:
    """Capable provider is healthy but field absent → provider_did_not_return."""
    paper = _empty_paper()
    caps = _caps("openalex", {_F.ABSTRACT: _S.FULL})
    health = {"openalex": _health(ProviderStatus.AVAILABLE)}
    annotate_missing(paper, queried=[caps], health=health)
    assert paper.missing_reasons.get("abstract") == "provider_did_not_return"


def test_provider_did_not_return_when_no_health_entry() -> None:
    """Capable provider with no health entry → falls through to provider_did_not_return."""
    paper = _empty_paper()
    caps = _caps("openalex", {_F.ABSTRACT: _S.FULL})
    # health dict is empty — provider is not MISSING_KEY and not FAILED
    annotate_missing(paper, queried=[caps], health={})
    assert paper.missing_reasons.get("abstract") == "provider_did_not_return"


# ---------------------------------------------------------------------------
# Present field is NOT annotated
# ---------------------------------------------------------------------------


def test_present_field_not_annotated() -> None:
    """A field that is populated should not appear in missing_reasons."""
    paper = NormalizedPaper(title="Present Title", source="openalex", abstract="Some abstract")
    caps = _caps("openalex", {_F.ABSTRACT: _S.FULL})
    annotate_missing(paper, queried=[caps], health={})
    assert "abstract" not in paper.missing_reasons


def test_citation_count_zero_is_treated_as_missing() -> None:
    """citation_count=0 is treated as absent (falsy int check)."""
    paper = _empty_paper()
    caps = _caps("openalex", {_F.CITATION_COUNT: _S.FULL})
    health = {"openalex": _health(ProviderStatus.AVAILABLE)}
    annotate_missing(paper, queried=[caps], health=health)
    assert "citation_count" in paper.missing_reasons


def test_non_empty_list_field_not_annotated() -> None:
    """A list field with entries should not appear in missing_reasons."""
    paper = NormalizedPaper(
        title="Paper",
        source="openalex",
        references=["10.1000/abc"],
    )
    caps = _caps("openalex", {_F.REFERENCES: _S.FULL})
    annotate_missing(paper, queried=[caps], health={})
    assert "references" not in paper.missing_reasons


# ---------------------------------------------------------------------------
# Idempotency: already-set reason is NOT overwritten
# ---------------------------------------------------------------------------


def test_existing_reason_not_overwritten() -> None:
    """A second annotate_missing call with different context should not overwrite reasons."""
    paper = _empty_paper()
    # First call: no providers → not_supported_by_any_queried_provider
    annotate_missing(paper, queried=[], health={})
    assert paper.missing_reasons.get("abstract") == "not_supported_by_any_queried_provider"

    # Second call: provider is capable and healthy → would be provider_did_not_return
    # but reason should not be overwritten.
    caps = _caps("openalex", {_F.ABSTRACT: _S.FULL})
    health = {"openalex": _health(ProviderStatus.AVAILABLE)}
    annotate_missing(paper, queried=[caps], health=health)
    # Still the original reason
    assert paper.missing_reasons.get("abstract") == "not_supported_by_any_queried_provider"


def test_annotate_missing_is_additive_not_destructive() -> None:
    """Calling annotate_missing twice should never remove existing entries."""
    paper = _empty_paper()
    caps = _caps("openalex", {_F.ABSTRACT: _S.FULL})
    annotate_missing(paper, queried=[caps], health={})
    reasons_after_first = dict(paper.missing_reasons)

    # Second call with empty queried — should not remove existing entries
    annotate_missing(paper, queried=[], health={})
    for key, value in reasons_after_first.items():
        assert paper.missing_reasons.get(key) == value


# ---------------------------------------------------------------------------
# P8.12-D: Fully populated paper → no missing reasons
# ---------------------------------------------------------------------------


def test_fully_populated_paper_no_missing_reasons() -> None:
    """A paper with all standard fields populated produces no missing_reasons."""
    paper = NormalizedPaper(
        title="Complete Paper",
        abstract="A detailed abstract that explains the study.",
        authors=[NormalizedAuthor(name="Jane Doe", family="Doe", given="Jane")],
        doi="10.1234/complete",
        year=2023,
        venue="Nature",
        citation_count=42,
        oa_url="https://example.com/paper.pdf",
        references=["10.1234/ref"],
        source="openalex",
    )
    annotate_missing(paper, queried=[OPENALEX_CAPS], health={})
    assert paper.missing_reasons == {}


# ---------------------------------------------------------------------------
# P8.12-D: Paper with no DOI → missing_reasons has "doi"
# ---------------------------------------------------------------------------


def test_paper_no_doi_annotated() -> None:
    """A paper missing doi gets an entry for 'doi' in missing_reasons."""
    paper = NormalizedPaper(title="No DOI Paper", source="openalex", doi=None)
    caps = _caps("openalex", {_F.DOI: _S.FULL})
    annotate_missing(paper, queried=[caps], health={})
    assert "doi" in paper.missing_reasons


# ---------------------------------------------------------------------------
# P8.12-D: Paper with no year → missing_reasons has "year"
# ---------------------------------------------------------------------------


def test_paper_no_year_annotated() -> None:
    """A paper missing year gets an entry for 'year' in missing_reasons."""
    paper = NormalizedPaper(title="No Year Paper", source="openalex", year=None)
    caps = _caps("openalex", {_F.YEAR: _S.FULL})
    annotate_missing(paper, queried=[caps], health={})
    assert "year" in paper.missing_reasons


# ---------------------------------------------------------------------------
# P8.12-D: annotate_missing mutates in place and returns None
# ---------------------------------------------------------------------------


def test_annotate_missing_returns_none_and_mutates_paper() -> None:
    """annotate_missing mutates the paper in place and has no return value."""
    paper = _empty_paper()
    result = annotate_missing(paper, queried=[], health={})
    assert result is None
    # The paper itself is mutated
    assert paper.missing_reasons != {}
