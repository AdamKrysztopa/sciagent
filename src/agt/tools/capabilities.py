"""Provider capability and health models for SciAgent search providers.

NOTE: Do not confuse SearchProviderCapabilities (this module) with
BaseSearchClient (src/agt/tools/base_search.py — the BASE SRU provider).

Two-layer design:
- ``SearchProviderCapabilities.fields`` — static declaration of what a provider
  *can* return, independent of any particular query.
- ``ProviderHealth`` — mutable runtime view updated on every search call.

The ``/providers`` endpoint returns both layers keyed by provider name.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class ProviderField(StrEnum):
    """Fields that a search provider may return for a paper."""

    TITLE = "title"
    ABSTRACT = "abstract"
    AUTHORS = "authors"
    DOI = "doi"
    YEAR = "year"
    VENUE = "venue"
    CITATION_COUNT = "citation_count"
    OA_URL = "oa_url"
    REFERENCES = "references"
    RELATED = "related"


class FieldSupport(StrEnum):
    """Degree of support a provider has for a given field."""

    FULL = "full"
    SHALLOW = "shallow"
    NONE = "none"


@dataclass(frozen=True)
class SearchProviderCapabilities:
    """Static capability declaration for a search provider.

    ``fields`` is a ``dict`` inside a ``frozen=True`` dataclass. The dataclass
    reference is immutable (cannot be reassigned), but the dict contents are
    mutable. Do not mutate ``fields`` after construction — treat it as read-only.
    MappingProxyType is intentionally avoided to preserve JSON serialisation
    compatibility with downstream patterns.
    """

    name: str
    fields: dict[ProviderField, FieldSupport]
    requires_key: bool = False
    key_env_var: str | None = None
    key_upgrade_hint: str | None = None
    notes: str = ""

    def supports(self, f: ProviderField) -> FieldSupport:
        """Return the FieldSupport level for the given field."""
        return self.fields.get(f, FieldSupport.NONE)


class ProviderStatus(StrEnum):
    """Runtime status of a provider."""

    AVAILABLE = "available"
    SHALLOW = "shallow"
    DISABLED = "disabled"
    MISSING_KEY = "missing_key"
    FAILED = "failed"
    RATE_LIMITED = "rate_limited"


class ProviderHealth(BaseModel):
    """Mutable runtime health state for a provider, updated on every search call."""

    model_config = ConfigDict(frozen=False)

    status: ProviderStatus = ProviderStatus.AVAILABLE
    reason: str = ""
    last_ok_at: float | None = None
    last_error_at: float | None = None
    consecutive_failures: int = 0
    retry_after: float | None = None


# ---------------------------------------------------------------------------
# Canonical capability tables
# ---------------------------------------------------------------------------

_F = ProviderField
_S = FieldSupport

OPENALEX_CAPS = SearchProviderCapabilities(
    name="openalex",
    fields={
        _F.TITLE: _S.FULL,
        _F.ABSTRACT: _S.FULL,
        _F.AUTHORS: _S.FULL,
        _F.DOI: _S.FULL,
        _F.YEAR: _S.FULL,
        _F.VENUE: _S.FULL,
        _F.CITATION_COUNT: _S.FULL,
        _F.OA_URL: _S.FULL,
        _F.REFERENCES: _S.NONE,
        _F.RELATED: _S.NONE,
    },
    notes=(
        "Polite pool access via mailto. "
        "Abstract reconstructed from inverted index. "
        "Year filter supported server-side."
    ),
)

CROSSREF_CAPS = SearchProviderCapabilities(
    name="crossref",
    fields={
        _F.TITLE: _S.FULL,
        _F.ABSTRACT: _S.NONE,
        _F.AUTHORS: _S.FULL,
        _F.DOI: _S.FULL,
        _F.YEAR: _S.FULL,
        _F.VENUE: _S.FULL,
        _F.CITATION_COUNT: _S.FULL,
        _F.OA_URL: _S.NONE,
        _F.REFERENCES: _S.NONE,
        _F.RELATED: _S.NONE,
    },
    notes="Abstract not part of standard Crossref Works response. Supports DOI and citation count.",
)

ARXIV_CAPS = SearchProviderCapabilities(
    name="arxiv",
    fields={
        _F.TITLE: _S.FULL,
        _F.ABSTRACT: _S.FULL,
        _F.AUTHORS: _S.FULL,
        _F.DOI: _S.NONE,
        _F.YEAR: _S.FULL,
        _F.VENUE: _S.NONE,
        _F.CITATION_COUNT: _S.NONE,
        _F.OA_URL: _S.FULL,
        _F.REFERENCES: _S.NONE,
        _F.RELATED: _S.NONE,
    },
    notes="All papers are open access. DOI not in Atom feed; arxiv_id is the identifier.",
)

EUROPE_PMC_CAPS = SearchProviderCapabilities(
    name="europe_pmc",
    fields={
        _F.TITLE: _S.FULL,
        _F.ABSTRACT: _S.FULL,
        _F.AUTHORS: _S.SHALLOW,
        _F.DOI: _S.FULL,
        _F.YEAR: _S.FULL,
        _F.VENUE: _S.NONE,
        _F.CITATION_COUNT: _S.FULL,
        _F.OA_URL: _S.FULL,
        _F.REFERENCES: _S.NONE,
        _F.RELATED: _S.NONE,
    },
    notes="Authors parsed from comma-separated string. PMC articles include PDF URL.",
)

DOAJ_CAPS = SearchProviderCapabilities(
    name="doaj",
    fields={
        _F.TITLE: _S.FULL,
        _F.ABSTRACT: _S.FULL,
        _F.AUTHORS: _S.FULL,
        _F.DOI: _S.FULL,
        _F.YEAR: _S.FULL,
        _F.VENUE: _S.FULL,
        _F.CITATION_COUNT: _S.NONE,
        _F.OA_URL: _S.FULL,
        _F.REFERENCES: _S.NONE,
        _F.RELATED: _S.NONE,
    },
    notes=(
        "Directory of Open Access Journals. "
        "All results are open access by definition. "
        "Citation count not tracked."
    ),
)

SEMANTIC_SCHOLAR_CAPS = SearchProviderCapabilities(
    name="semantic_scholar",
    fields={
        _F.TITLE: _S.FULL,
        _F.ABSTRACT: _S.FULL,
        _F.AUTHORS: _S.FULL,
        _F.DOI: _S.FULL,
        _F.YEAR: _S.FULL,
        _F.VENUE: _S.FULL,
        _F.CITATION_COUNT: _S.FULL,
        _F.OA_URL: _S.FULL,
        _F.REFERENCES: _S.SHALLOW,
        _F.RELATED: _S.SHALLOW,
    },
    key_env_var="AGT_SEMANTIC_SCHOLAR_API_KEY",
    key_upgrade_hint=(
        "Set AGT_SEMANTIC_SCHOLAR_API_KEY for higher authenticated throughput "
        "and more reliable access for citation-heavy queries."
    ),
    notes=(
        "Keyless search available at reduced rate limits. "
        "References and recommendations available via separate API calls."
    ),
)

CORE_PUBLIC_CAPS = SearchProviderCapabilities(
    name="core",
    fields={
        _F.TITLE: _S.FULL,
        _F.ABSTRACT: _S.FULL,
        _F.AUTHORS: _S.FULL,
        _F.DOI: _S.FULL,
        _F.YEAR: _S.FULL,
        _F.VENUE: _S.NONE,
        _F.CITATION_COUNT: _S.NONE,
        _F.OA_URL: _S.FULL,
        _F.REFERENCES: _S.NONE,
        _F.RELATED: _S.NONE,
    },
    requires_key=True,
    key_env_var="AGT_CORE_API_KEY",
    key_upgrade_hint=(
        "Set AGT_CORE_API_KEY to enable CORE full-text open-access repository search."
    ),
    notes="API key required. All results are open access or preprints.",
)

PUBMED_CAPS = SearchProviderCapabilities(
    name="pubmed",
    fields={
        _F.TITLE: _S.FULL,
        _F.ABSTRACT: _S.FULL,
        _F.AUTHORS: _S.FULL,
        _F.DOI: _S.FULL,
        _F.YEAR: _S.FULL,
        _F.VENUE: _S.FULL,
        _F.CITATION_COUNT: _S.NONE,
        _F.OA_URL: _S.SHALLOW,
        _F.REFERENCES: _S.NONE,
        _F.RELATED: _S.NONE,
    },
    key_env_var="AGT_NCBI_API_KEY",
    key_upgrade_hint=(
        "Set AGT_NCBI_API_KEY for higher PubMed request limits (10 req/s vs 3 req/s)."
    ),
    notes=("Two-step retrieval: esearch + efetch. OA URL available for PMC articles only."),
)

BASE_CAPS = SearchProviderCapabilities(
    name="base",
    fields={
        _F.TITLE: _S.FULL,
        _F.ABSTRACT: _S.SHALLOW,
        _F.AUTHORS: _S.SHALLOW,
        _F.DOI: _S.SHALLOW,
        _F.YEAR: _S.SHALLOW,
        _F.VENUE: _S.NONE,
        _F.CITATION_COUNT: _S.NONE,
        _F.OA_URL: _S.SHALLOW,
        _F.REFERENCES: _S.NONE,
        _F.RELATED: _S.NONE,
    },
    notes=(
        "Bielefeld Academic Search Engine SRU API. "
        "Field quality is variable across records. "
        "Single creator field; abstract from description element."
    ),
)

OPENCITATIONS_CAPS = SearchProviderCapabilities(
    name="opencitations",
    fields={
        _F.TITLE: _S.NONE,
        _F.ABSTRACT: _S.NONE,
        _F.AUTHORS: _S.NONE,
        _F.DOI: _S.SHALLOW,
        _F.YEAR: _S.NONE,
        _F.VENUE: _S.NONE,
        _F.CITATION_COUNT: _S.FULL,
        _F.OA_URL: _S.NONE,
        _F.REFERENCES: _S.FULL,
        _F.RELATED: _S.NONE,
    },
    notes=(
        "Not a search provider. "
        "Used exclusively for DOI-based citation-count enrichment "
        "and reference retrieval after primary retrieval."
    ),
)

DIMENSIONS_CAPS = SearchProviderCapabilities(
    name="dimensions",
    fields={
        _F.TITLE: _S.FULL,
        _F.ABSTRACT: _S.FULL,
        _F.AUTHORS: _S.SHALLOW,
        _F.DOI: _S.FULL,
        _F.YEAR: _S.FULL,
        _F.VENUE: _S.SHALLOW,
        _F.CITATION_COUNT: _S.FULL,
        _F.OA_URL: _S.NONE,
        _F.REFERENCES: _S.NONE,
        _F.RELATED: _S.NONE,
    },
    requires_key=True,
    key_env_var="AGT_DIMENSIONS_KEY",
    key_upgrade_hint=(
        "Set AGT_DIMENSIONS_KEY to enable Dimensions citation, funding, and institutional metadata."
    ),
    notes=(
        "Paid/institutional access. "
        "Adds funding, clinical trial, and patent context where available."
    ),
)

GOOGLE_SCHOLAR_CAPS = SearchProviderCapabilities(
    name="google_scholar",
    fields={
        _F.TITLE: _S.FULL,
        _F.ABSTRACT: _S.SHALLOW,
        _F.AUTHORS: _S.SHALLOW,
        _F.DOI: _S.NONE,
        _F.YEAR: _S.SHALLOW,
        _F.VENUE: _S.NONE,
        _F.CITATION_COUNT: _S.FULL,
        _F.OA_URL: _S.SHALLOW,
        _F.REFERENCES: _S.NONE,
        _F.RELATED: _S.NONE,
    },
    requires_key=True,
    key_env_var="AGT_SERPAPI_KEY",
    key_upgrade_hint=(
        "Set AGT_SERPAPI_KEY to enable Google Scholar via SerpAPI "
        "for grey-literature and Scholar-ranking coverage."
    ),
    notes=(
        "Requires SerpAPI subscription. Abstract is a snippet; authors parsed from citation string."
    ),
)

# ---------------------------------------------------------------------------
# Public registry — ordered by baseline tier then optional providers
# ---------------------------------------------------------------------------

ALL_PROVIDER_CAPS: dict[str, SearchProviderCapabilities] = {
    caps.name: caps
    for caps in [
        OPENALEX_CAPS,
        CROSSREF_CAPS,
        ARXIV_CAPS,
        EUROPE_PMC_CAPS,
        DOAJ_CAPS,
        SEMANTIC_SCHOLAR_CAPS,
        CORE_PUBLIC_CAPS,
        PUBMED_CAPS,
        BASE_CAPS,
        OPENCITATIONS_CAPS,
        DIMENSIONS_CAPS,
        GOOGLE_SCHOLAR_CAPS,
    ]
}
