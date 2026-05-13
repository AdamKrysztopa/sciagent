"""Missing-field annotation for NormalizedPaper results.

Fills paper.missing_reasons with a reason code for every null/empty
field that a queried provider COULD have returned. Called after merge.

Reason codes
------------
provider_did_not_return          Capable provider queried but field was absent
not_supported_by_any_queried_provider  No queried provider declares support
missing_key                      Only key-gated providers support this field
provider_failed                  Capable provider errored or was rate-limited
not_requested_at_depth           Current depth profile skips this enrichment
"""

from __future__ import annotations

from agt.models import NormalizedPaper
from agt.tools.capabilities import (
    FieldSupport,
    ProviderField,
    ProviderHealth,
    ProviderStatus,
    SearchProviderCapabilities,
)

# Maps each ProviderField to the NormalizedPaper attribute name it covers.
FIELD_TO_ATTR: dict[ProviderField, str] = {
    ProviderField.TITLE: "title",
    ProviderField.ABSTRACT: "abstract",
    ProviderField.AUTHORS: "authors",
    ProviderField.DOI: "doi",
    ProviderField.YEAR: "year",
    ProviderField.VENUE: "venue",
    ProviderField.CITATION_COUNT: "citation_count",
    ProviderField.OA_URL: "oa_url",
    ProviderField.REFERENCES: "references",
}


def _is_present(value: object) -> bool:
    """Return True when a field value is considered populated."""
    if value is None:
        return False
    if isinstance(value, int):
        return value > 0
    if isinstance(value, (list, dict)):
        return bool(value)  # pyright: ignore[reportUnknownArgumentType]
    if isinstance(value, str):
        return value != ""
    return True


def _classify_reason(
    field: ProviderField,
    queried: list[SearchProviderCapabilities],
    health: dict[str, ProviderHealth],
) -> str:
    """Return a reason code for why a field is missing."""
    capable = [p for p in queried if p.supports(field) != FieldSupport.NONE]

    if not capable:
        return "not_supported_by_any_queried_provider"

    # If all capable providers require a key and are missing it, surface that.
    all_missing_key = all(
        (h := health.get(p.name)) is not None and h.status == ProviderStatus.MISSING_KEY
        for p in capable
    )
    if all_missing_key:
        return "missing_key"

    # If any capable provider failed or was rate-limited, surface that.
    any_failed = any(
        (h := health.get(p.name)) is not None
        and h.status in (ProviderStatus.FAILED, ProviderStatus.RATE_LIMITED)
        for p in capable
    )
    if any_failed:
        return "provider_failed"

    return "provider_did_not_return"


def annotate_missing(
    paper: NormalizedPaper,
    *,
    queried: list[SearchProviderCapabilities],
    health: dict[str, ProviderHealth],
    profile_skipped: set[ProviderField] | None = None,
) -> None:
    """Fill paper.missing_reasons for every null/empty field.

    Mutates paper.missing_reasons in place. Already-set reasons are
    preserved (not overwritten). Only annotates fields that are absent.

    Parameters
    ----------
    paper:
        The paper to annotate. Only null/empty fields are touched.
    queried:
        Capability tables for providers that were actually queried in this run.
    health:
        Runtime health snapshot per provider name, keyed by provider name.
    profile_skipped:
        ProviderField values that the current depth profile skips entirely
        (e.g. REFERENCES when expand_refs=False).
    """
    skipped = profile_skipped or set()
    reasons: dict[str, str] = {}

    for field, attr in FIELD_TO_ATTR.items():
        value = getattr(paper, attr, None)
        if _is_present(value):
            continue
        # Skip fields already annotated by a previous pass.
        if attr in paper.missing_reasons:
            continue

        if field in skipped:
            reasons[attr] = "not_requested_at_depth"
            continue

        reasons[attr] = _classify_reason(field, queried, health)

    paper.missing_reasons.update(reasons)
