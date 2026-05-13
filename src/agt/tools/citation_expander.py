"""Citation graph expansion for seed DOIs.

Resolves outgoing references and incoming citations for a set of seed DOIs
using the OpenCitations COCI API, then fetches full metadata from OpenAlex.

Usage::

    papers = await expand_citations(
        seed_dois=["10.1000/xyz123"],
        settings=settings,
        limit_per_doi=10,
        direction="both",
    )
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import Literal, cast

import httpx

from agt.config import Settings, get_settings
from agt.models import NormalizedAuthor, NormalizedPaper
from agt.tools.opencitations import OpenCitationsClient

_OA_WORKS_BASE = "https://api.openalex.org/works"
_BATCH_SIZE = 50  # OpenAlex filter= supports up to ~50 DOIs
_HTTP_OK = 200


async def fetch_openalex_by_dois(
    dois: list[str],
    *,
    mailto: str | None,
) -> list[NormalizedPaper]:
    """Fetch NormalizedPaper records from OpenAlex for a list of DOIs."""
    if not dois:
        return []

    headers: dict[str, str] = {}
    if mailto:
        headers["User-Agent"] = f"SciAgent/0.1 mailto:{mailto}"

    papers: list[NormalizedPaper] = []
    for i in range(0, len(dois), _BATCH_SIZE):
        batch = dois[i : i + _BATCH_SIZE]
        doi_filter = "|".join(f"doi:{d}" for d in batch)
        params: dict[str, str | int] = {
            "filter": doi_filter,
            "per-page": len(batch),
            "select": "id,doi,title,authorships,publication_year,primary_location,cited_by_count,abstract_inverted_index,concepts",
        }
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(_OA_WORKS_BASE, params=params, headers=headers)
                if response.status_code != _HTTP_OK:
                    continue
                raw: object = response.json()
        except Exception:  # pragma: no cover
            continue

        if not isinstance(raw, dict):
            continue
        data = cast(dict[str, object], raw)
        results_raw = data.get("results", [])
        if not isinstance(results_raw, list):
            continue
        results = cast(list[object], results_raw)

        for item in results:
            paper = parse_oa_item(item)
            if paper is not None:
                papers.append(paper)

    return papers


def parse_oa_item(item: object) -> NormalizedPaper | None:
    """Parse a single OpenAlex work item into a NormalizedPaper."""
    if not isinstance(item, dict):
        return None
    work = cast(dict[str, object], item)

    title_raw = work.get("title", "")
    if not isinstance(title_raw, str) or not title_raw.strip():
        return None

    doi_raw = work.get("doi", "")
    doi: str | None = None
    if isinstance(doi_raw, str) and doi_raw:
        doi = doi_raw.replace("https://doi.org/", "").strip() or None

    year_raw = work.get("publication_year")
    year: int | None = int(year_raw) if isinstance(year_raw, int) else None

    citation_count_raw = work.get("cited_by_count", 0)
    citation_count: int = int(citation_count_raw) if isinstance(citation_count_raw, int) else 0

    authors: list[NormalizedAuthor] = []
    authorships_raw = work.get("authorships", [])
    if isinstance(authorships_raw, list):
        for auth_raw in cast(list[object], authorships_raw):
            if not isinstance(auth_raw, dict):
                continue
            auth = cast(dict[str, object], auth_raw)
            author_obj_raw = auth.get("author", {})
            if not isinstance(author_obj_raw, dict):
                continue
            author_obj = cast(dict[str, object], author_obj_raw)
            display_name = author_obj.get("display_name", "")
            if not isinstance(display_name, str):
                continue
            oa_id_raw = author_obj.get("id", "")
            oa_id: str | None = None
            if isinstance(oa_id_raw, str):
                oa_id = oa_id_raw.replace("https://openalex.org/", "") or None
            orcid_raw = author_obj.get("orcid")
            orcid: str | None = None
            if isinstance(orcid_raw, str):
                orcid = orcid_raw.replace("https://orcid.org/", "") or None
            name_parts = display_name.rsplit(" ", 1)
            authors.append(
                NormalizedAuthor(
                    name=display_name,
                    family=name_parts[-1] if name_parts else None,
                    given=name_parts[0] if len(name_parts) > 1 else None,
                    orcid=orcid,
                    openalex_id=oa_id,
                    source="openalex",
                )
            )

    loc_raw = work.get("primary_location", {})
    oa_url: str | None = None
    if isinstance(loc_raw, dict):
        loc = cast(dict[str, object], loc_raw)
        pdf_url = loc.get("pdf_url")
        if isinstance(pdf_url, str):
            oa_url = pdf_url

    return NormalizedPaper(
        title=title_raw.strip(),
        doi=doi,
        year=year,
        authors=authors,
        citation_count=citation_count,
        oa_url=oa_url,
        source="openalex",
        sources=["openalex"],
    )


async def expand_citations(
    seed_dois: list[str],
    *,
    settings: Settings | None = None,
    limit_per_doi: int = 10,
    direction: Literal["references", "cited_by", "both"] = "both",
) -> list[NormalizedPaper]:
    """Expand seed DOIs into related papers via the OpenCitations citation graph.

    For each seed DOI, retrieves its outgoing references and/or incoming
    citations, then fetches full metadata from OpenAlex for each found DOI.

    Parameters
    ----------
    seed_dois:
        List of DOIs to expand. Empty list returns [].
    settings:
        Settings instance. Defaults to :func:`get_settings`.
    limit_per_doi:
        Max DOIs to expand per seed (default 10). Applied per direction.
    direction:
        Which direction to expand: outgoing references, incoming citations, or both.

    Returns
    -------
    list[NormalizedPaper]
        Papers found via citation expansion, each with ``citation_relation`` set.
    """
    if not seed_dois:
        return []

    active = settings or get_settings()
    oc = OpenCitationsClient(
        timeout_seconds=int(active.runtime.timeout_seconds),
        retries=active.runtime.retries,
    )

    refs_map: dict[str, list[str]] = {}
    citing_map: dict[str, list[str]] = {}

    async def _expand_one(seed: str) -> None:
        refs: list[str] = []
        cits: list[str] = []

        if direction in ("references", "both"):
            with contextlib.suppress(Exception):  # pragma: no cover
                refs = await oc.references(seed)
        if direction in ("cited_by", "both"):
            with contextlib.suppress(Exception):  # pragma: no cover
                cits = await oc.citations(seed)

        refs_map[seed] = refs[:limit_per_doi]
        citing_map[seed] = cits[:limit_per_doi]

    await asyncio.gather(*[_expand_one(seed) for seed in seed_dois])

    refs_dois: set[str] = set()
    cited_by_dois: set[str] = set()
    for refs in refs_map.values():
        refs_dois.update(refs)
    for cits in citing_map.values():
        cited_by_dois.update(cits)

    seed_set = {d.lower() for d in seed_dois}
    refs_dois = {d for d in refs_dois if d.lower() not in seed_set}
    cited_by_dois = {d for d in cited_by_dois if d.lower() not in seed_set}

    refs_papers, cited_papers = await asyncio.gather(
        fetch_openalex_by_dois(list(refs_dois), mailto=active.mailto),
        fetch_openalex_by_dois(list(cited_by_dois), mailto=active.mailto),
    )

    tagged: list[NormalizedPaper] = []
    for p in refs_papers:
        tagged.append(p.model_copy(update={"citation_relation": "references"}))
    for p in cited_papers:
        tagged.append(p.model_copy(update={"citation_relation": "cited_by"}))

    return tagged
