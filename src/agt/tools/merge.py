"""Field-level merge with provenance preservation.

When in doubt: keep both values and flag a conflict rather than
silently picking one. The Zotero sidebar surfaces conflicts on approve.
"""

from __future__ import annotations

import re
from typing import cast

from agt.models import (
    FieldConflict,
    FieldConflictValue,
    ItemType,
    NormalizedAuthor,
    NormalizedPaper,
)

# ---------------------------------------------------------------------------
# Provider priority — lower index = higher authority for tie-breaking
# ---------------------------------------------------------------------------

PROVIDER_PRIORITY: list[str] = [
    "crossref",
    "openalex",
    "europe_pmc",
    "pubmed",
    "doaj",
    "semantic_scholar",
    "arxiv",
    "core",
    "base",
    "dimensions",
    "google_scholar",
]

# ---------------------------------------------------------------------------
# Thresholds (no magic numbers)
# ---------------------------------------------------------------------------

_TITLE_JACCARD_MIN: float = 0.85
_TITLE_CONFLICT_THRESHOLD: float = 0.8
_MAX_YEAR_DELTA: int = 1
_MIN_DOI_CLUSTER_SIZE: int = 2

_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------


def _priority(name: str) -> int:
    """Return the provider's priority index (lower = higher authority)."""
    try:
        return PROVIDER_PRIORITY.index(name)
    except ValueError:
        return 99


def _norm_doi(doi: str | None) -> str:
    """Normalize DOI for comparison (lowercase, stripped)."""
    if doi is None:
        return ""
    return doi.strip().lower()


def _norm_title(t: str) -> str:
    """Lowercase, collapse whitespace, strip punctuation."""
    t = t.lower()
    t = _PUNCT_RE.sub("", t)
    return " ".join(t.split())


def _jaccard(a: str, b: str) -> float:
    """Word-level Jaccard similarity between normalized titles."""
    na, nb = _norm_title(a), _norm_title(b)
    if not na and not nb:
        return 1.0
    if not na or not nb:
        return 0.0
    words_a = set(na.split())
    words_b = set(nb.split())
    intersection = len(words_a & words_b)
    union = len(words_a | words_b)
    return intersection / union if union > 0 else 0.0


# ---------------------------------------------------------------------------
# Clustering helpers
# ---------------------------------------------------------------------------


def _papers_match(a: NormalizedPaper, b: NormalizedPaper) -> bool:
    """Return True when two DOI-less papers are likely the same work."""
    if _jaccard(a.title, b.title) < _TITLE_JACCARD_MIN:
        return False
    if a.year is not None and b.year is not None and abs(a.year - b.year) > _MAX_YEAR_DELTA:
        return False
    a_lasts = {auth.normalized_last() for auth in a.authors if auth.normalized_last()}
    b_lasts = {auth.normalized_last() for auth in b.authors if auth.normalized_last()}
    return not (a_lasts and b_lasts and not a_lasts & b_lasts)


def _find(parent: list[int], x: int) -> int:
    """Union-find: path-compressed find."""
    root = x
    while parent[root] != root:
        root = parent[root]
    while parent[x] != root:
        next_x = parent[x]
        parent[x] = root
        x = next_x
    return root


def _union(parent: list[int], x: int, y: int) -> None:
    """Union-find: merge two components."""
    px, py = _find(parent, x), _find(parent, y)
    if px != py:
        parent[py] = px


def cluster(papers: list[NormalizedPaper]) -> list[list[NormalizedPaper]]:
    """Partition papers into clusters of likely-duplicate records.

    Pass 1: exact DOI grouping (normalized lowercase).
    Pass 2: title + year + shared-author-last fuzzy grouping for papers
            without a shared DOI.
    """
    doi_groups: dict[str, list[NormalizedPaper]] = {}
    no_doi: list[NormalizedPaper] = []

    for paper in papers:
        ndoi = _norm_doi(paper.doi)
        if ndoi:
            doi_groups.setdefault(ndoi, []).append(paper)
        else:
            no_doi.append(paper)

    clusters: list[list[NormalizedPaper]] = []
    for group in doi_groups.values():
        if len(group) >= _MIN_DOI_CLUSTER_SIZE:
            clusters.append(group)
        else:
            no_doi.append(group[0])

    if not no_doi:
        return clusters

    parent = list(range(len(no_doi)))
    for i in range(len(no_doi)):
        for j in range(i + 1, len(no_doi)):
            if _papers_match(no_doi[i], no_doi[j]):
                _union(parent, i, j)

    group_map: dict[int, list[NormalizedPaper]] = {}
    for i, paper in enumerate(no_doi):
        root = _find(parent, i)
        group_map.setdefault(root, []).append(paper)

    return clusters + list(group_map.values())


# ---------------------------------------------------------------------------
# Per-field merge helpers
# ---------------------------------------------------------------------------


def _merge_doi(
    sorted_papers: list[NormalizedPaper],
) -> tuple[str | None, list[FieldConflict]]:
    """First non-null DOI by priority; conflict if multiple distinct DOIs."""
    first_doi: str | None = None
    conflict_values: list[FieldConflictValue] = []
    seen_norm: set[str] = set()

    for p in sorted_papers:
        if p.doi is None:
            continue
        ndoi = _norm_doi(p.doi)
        if not ndoi:
            continue
        if first_doi is None:
            first_doi = p.doi
        if ndoi not in seen_norm:
            conflict_values.append(FieldConflictValue(provider=p.source, value=p.doi))
            seen_norm.add(ndoi)

    if not conflict_values:
        return None, []

    conflicts: list[FieldConflict] = []
    if len(conflict_values) > 1:
        conflicts.append(FieldConflict(field="doi", values=conflict_values))
    return first_doi, conflicts


def _merge_title(
    sorted_papers: list[NormalizedPaper],
) -> tuple[str, list[FieldConflict]]:
    """Longest non-empty title wins; conflict if any runner-up has Jaccard < threshold."""
    titles: list[tuple[str, str]] = [(p.title, p.source) for p in sorted_papers if p.title.strip()]
    if not titles:
        return sorted_papers[0].title, []

    selected_title, selected_source = max(titles, key=lambda x: len(x[0]))

    conflict_values: list[FieldConflictValue] = []
    for title, source in titles:
        if title == selected_title:
            continue
        if _jaccard(selected_title, title) < _TITLE_CONFLICT_THRESHOLD:
            conflict_values.append(FieldConflictValue(provider=source, value=title))

    conflicts: list[FieldConflict] = []
    if conflict_values:
        conflict_values.insert(
            0, FieldConflictValue(provider=selected_source, value=selected_title)
        )
        conflicts.append(FieldConflict(field="title", values=conflict_values))

    return selected_title, conflicts


def _merge_year(
    sorted_papers: list[NormalizedPaper],
) -> tuple[int | None, list[FieldConflict]]:
    """Year from highest-priority provider; conflict if any other disagrees."""
    year_values: list[tuple[int, str]] = [
        (p.year, p.source) for p in sorted_papers if p.year is not None
    ]
    if not year_values:
        return None, []

    primary_year, primary_source = year_values[0]
    conflict_values: list[FieldConflictValue] = []
    for year, source in year_values[1:]:
        if year != primary_year:
            conflict_values.append(FieldConflictValue(provider=source, value=year))

    conflicts: list[FieldConflict] = []
    if conflict_values:
        conflict_values.insert(0, FieldConflictValue(provider=primary_source, value=primary_year))
        conflicts.append(FieldConflict(field="year", values=conflict_values))

    return primary_year, conflicts


def _merge_abstract(sorted_papers: list[NormalizedPaper]) -> str | None:
    """Longest non-empty abstract wins (best-effort, no conflict recorded)."""
    abstracts = [p.abstract for p in sorted_papers if p.abstract and p.abstract.strip()]
    if not abstracts:
        return None
    return max(abstracts, key=len)


def _merge_citation_count(sorted_papers: list[NormalizedPaper]) -> int:
    """Max citation count across the cluster."""
    return max((p.citation_count for p in sorted_papers), default=0)


def _merge_influential_citation_count(sorted_papers: list[NormalizedPaper]) -> int:
    """Max influential citation count across the cluster."""
    return max((p.influential_citation_count for p in sorted_papers), default=0)


def _merge_open_access(sorted_papers: list[NormalizedPaper]) -> bool:
    """True if any provider reports open access."""
    return any(p.open_access for p in sorted_papers)


# ---------------------------------------------------------------------------
# Author merge helpers
# ---------------------------------------------------------------------------


def _author_key(author: NormalizedAuthor) -> str:
    """Stable identity key for deduplicating authors across providers."""
    if author.orcid:
        return f"orcid:{author.orcid}"
    last = author.normalized_last()
    given_init = (author.given or "")[:1].lower()
    return f"name:{last}|{given_init}"


def _enrich_author(base: NormalizedAuthor, extra: NormalizedAuthor) -> NormalizedAuthor:
    """Copy missing identifier fields from *extra* into *base*."""
    updates: dict[str, object] = {}
    if base.orcid is None and extra.orcid is not None:
        updates["orcid"] = extra.orcid
    if base.openalex_id is None and extra.openalex_id is not None:
        updates["openalex_id"] = extra.openalex_id
    if base.s2_author_id is None and extra.s2_author_id is not None:
        updates["s2_author_id"] = extra.s2_author_id
    if base.affiliation is None and extra.affiliation is not None:
        updates["affiliation"] = extra.affiliation
    if not updates:
        return base
    return base.model_copy(update=updates)


def _merge_authors(sorted_papers: list[NormalizedPaper]) -> list[NormalizedAuthor]:
    """Union authors by ORCID or (normalized-last, given-initial) key."""
    seen: dict[str, NormalizedAuthor] = {}
    for paper in sorted_papers:
        for author in paper.authors:
            key = _author_key(author)
            if key in seen:
                seen[key] = _enrich_author(seen[key], author)
            else:
                seen[key] = author
    return list(seen.values())


def _merge_references(papers: list[NormalizedPaper]) -> list[str]:
    """Deduplicated union of reference lists (insertion-order preserved)."""
    seen: set[str] = set()
    result: list[str] = []
    for paper in papers:
        for ref in paper.references:
            if ref not in seen:
                seen.add(ref)
                result.append(ref)
    return result


# ---------------------------------------------------------------------------
# Cluster merge
# ---------------------------------------------------------------------------


def merge_cluster(papers: list[NormalizedPaper]) -> NormalizedPaper:
    """Merge a cluster of duplicate records into a single canonical paper."""
    sorted_papers = sorted(papers, key=lambda p: _priority(p.source))
    primary = sorted_papers[0]

    doi, doi_conflicts = _merge_doi(sorted_papers)
    title, title_conflicts = _merge_title(sorted_papers)
    year, year_conflicts = _merge_year(sorted_papers)

    all_conflicts = doi_conflicts + title_conflicts + year_conflicts

    abstract = _merge_abstract(sorted_papers)
    citation_count = _merge_citation_count(sorted_papers)
    influential_citation_count = _merge_influential_citation_count(sorted_papers)
    open_access = _merge_open_access(sorted_papers)
    authors = _merge_authors(sorted_papers)
    references = _merge_references(sorted_papers)
    sources = sorted({p.source for p in papers})

    url = next((p.url for p in sorted_papers if p.url), None)
    oa_url = next((p.oa_url for p in sorted_papers if p.oa_url), None)
    venue = next((p.venue for p in sorted_papers if p.venue), None)
    pdf_url = next((p.pdf_url for p in sorted_papers if p.pdf_url), None)
    arxiv_id = next((p.arxiv_id for p in sorted_papers if p.arxiv_id), None)
    item_type: ItemType | None = cast(
        "ItemType | None",
        next((p.item_type for p in sorted_papers if p.item_type is not None), None),
    )
    volume = next((p.volume for p in sorted_papers if p.volume), None)
    issue = next((p.issue for p in sorted_papers if p.issue), None)
    pages = next((p.pages for p in sorted_papers if p.pages), None)

    # external_ids: later providers (lower priority) overwrite earlier ones per spec
    external_ids: dict[str, str] = {}
    for p in sorted_papers:
        external_ids.update(p.external_ids)

    semantic_score = max(p.semantic_score for p in sorted_papers)

    return NormalizedPaper(
        title=title,
        year=year,
        doi=doi,
        arxiv_id=arxiv_id,
        abstract=abstract,
        authors=authors,
        url=url,
        pdf_url=pdf_url,
        source=primary.source,
        semantic_score=semantic_score,
        citation_count=citation_count,
        influential_citation_count=influential_citation_count,
        open_access=open_access,
        venue=venue,
        item_type=item_type,
        volume=volume,
        issue=issue,
        pages=pages,
        oa_url=oa_url,
        references=references,
        external_ids=external_ids,
        sources=sources,
        conflicts=all_conflicts,
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def merge(papers: list[NormalizedPaper]) -> list[NormalizedPaper]:
    """Cluster duplicates and merge each cluster into one canonical paper."""
    return [merge_cluster(c) for c in cluster(papers)]
