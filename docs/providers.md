# Provider Inventory

SciAgent federates academic literature search across eleven sources. The guiding principle is a
**no-key baseline**: five providers (OpenAlex, Crossref, arXiv, Europe PMC, BASE) require no
credentials and form the default retrieval tier. Three providers (Semantic Scholar, PubMed) work
keylessly with rate-limited public quotas and accept an optional API key for higher throughput.
Three providers (CORE, Dimensions, Google Scholar via SerpAPI) require a paid or registered API
key and are activated only when the corresponding environment variable is set.

OpenCitations is not a search provider; it is used exclusively for DOI-based citation-count
enrichment after the primary retrieval step.

## Summary Table

| Provider | Client Class | Base URL | Auth Model | Key Env Var | Retry Wiring | Fields Populated |
| -------- | ------------ | -------- | ---------- | ----------- | ------------ | ---------------- |
| OpenAlex | `OpenAlexClient` | `https://api.openalex.org` | Keyless | — | tenacity, exp backoff | title, abstract, authors, doi, year, venue, citation_count, open_access, url |
| Crossref | `CrossrefClient` | `https://api.crossref.org` | Keyless | — | tenacity, exp backoff | title, authors, doi, year, venue, citation_count |
| arXiv | `ArxivClient` | `https://export.arxiv.org/api/query` | Keyless | — | tenacity, exp backoff | title, abstract, authors, year, url, arxiv_id |
| Europe PMC | `EuropePMCClient` | `https://www.ebi.ac.uk/europepmc/webservices/rest` | Keyless | — | tenacity, exp backoff | title, abstract, authors, doi, year, url, citation_count, open_access |
| PubMed | `PubMedClient` | `https://eutils.ncbi.nlm.nih.gov/entrez/eutils` | Keyless (optional key) | `AGT_NCBI_API_KEY` | tenacity, exp backoff | title, abstract, authors, doi, year, venue |
| BASE | `BaseSearchClient` | `https://api.base-search.net/cgi-bin/BaseHttpSearchInterface.fcgi` | Keyless | — | tenacity, exp backoff | title, abstract, authors, doi, year, url |
| Semantic Scholar | `SemanticScholarClient` | `https://api.semanticscholar.org/graph/v1` | Keyless (optional key) | `AGT_SEMANTIC_SCHOLAR_API_KEY` | tenacity, exp backoff | title, abstract, authors, doi, year, venue, citation_count, open_access, url |
| OpenCitations | `OpenCitationsClient` | `https://opencitations.net/index/coci/api/v1` | Keyless | — | tenacity, exp backoff | citation_count (by DOI) |
| CORE | `CoreClient` | `https://api.core.ac.uk/v3` | API key required | `AGT_CORE_API_KEY` | tenacity, exp backoff | title, abstract, authors, doi, year, url, open_access |
| Dimensions | `DimensionsClient` | `https://app.dimensions.ai/api` | API key required | `AGT_DIMENSIONS_KEY` | tenacity, exp backoff | title, authors, doi, year, citation_count |
| Google Scholar | `GoogleScholarClient` | `https://serpapi.com/search.json` | API key required | `AGT_SERPAPI_KEY` | tenacity, exp backoff | title, abstract, authors, year, url, citation_count |

## OpenAlexClient

**Base URL:** `https://api.openalex.org`

**Auth:** Keyless. No API key required. Polite pool access is automatic when a contact email is
provided in the `mailto` header (future enhancement).

**Key env var:** None.

**Fields populated:** `title` (HTML tags stripped), `abstract` (reconstructed from inverted
index), `authors` (from `authorships[].author.display_name`), `doi`, `year`
(`publication_year`), `venue` (`primary_location.source.display_name`), `citation_count`
(`cited_by_count`), `open_access` (`open_access.is_oa`), `url`
(`primary_location.landing_page_url`).

**Retry / timeout:** tenacity `AsyncRetrying` with exponential back-off (1 s min, 8 s max),
retries on `httpx.TimeoutException`, `httpx.NetworkError`, and `httpx.HTTPStatusError`, `reraise=True`.

**Notes:** Supports cursor-based multi-page retrieval via `max_pages`. Year filter uses the
`filter=publication_year:>N` param. Abstract reconstruction joins tokens from
`abstract_inverted_index` in position order.

## CrossrefClient

**Base URL:** `https://api.crossref.org`

**Auth:** Keyless. No API key required.

**Key env var:** None.

**Fields populated:** `title` (first element of the `title` list), `authors` (from `author[]`
`given`+`family`), `doi`, `year` (from `published-print` or `published-online` date-parts),
`venue` (`container-title`), `citation_count` (`is-referenced-by-count`).

**Retry / timeout:** tenacity `AsyncRetrying` with exponential back-off, retries on
`httpx.TimeoutException`, `httpx.NetworkError`, and `httpx.HTTPStatusError`, `reraise=True`.

**Notes:** Supports offset-based multi-page retrieval via `max_pages`. Abstract is not part of
the standard Crossref Works response and is not populated.

## ArxivClient

**Base URL:** `https://export.arxiv.org/api/query`

**Auth:** Keyless. No API key required.

**Key env var:** None.

**Fields populated:** `title` (whitespace-normalised), `abstract` (`<summary>`), `authors`
(`<author><name>`), `year` (first four digits of `<published>`), `url` (`<id>` entry URL),
`arxiv_id` (last path segment of the entry ID), `open_access` always `True`.

**Retry / timeout:** tenacity `AsyncRetrying` with exponential back-off, retries on
`httpx.TimeoutException`, `httpx.NetworkError`, and `httpx.HTTPStatusError`, `reraise=True`.
A mandatory `asyncio.sleep(3.0)` delay per request respects arXiv's burst-traffic guidance.

**Notes:** Category filter is appended as `AND (cat:cs.AI OR ...)` when `categories` is provided.
DOI is not part of the arXiv Atom feed; `arxiv_id` serves as the paper identifier.

## EuropePMCClient

**Base URL:** `https://www.ebi.ac.uk/europepmc/webservices/rest`

**Auth:** Keyless. No API key required.

**Key env var:** None.

**Fields populated:** `title`, `abstract` (`abstractText`), `authors` (split from
`authorString`), `doi`, `year` (`pubYear`), `url` (constructed as
`https://europepmc.org/article/{source}/{id}`), `citation_count` (`citedByCount`),
`open_access` (`isOpenAccess == "Y"` or PMC ID present).

**Retry / timeout:** tenacity `AsyncRetrying` with exponential back-off, retries on
`httpx.TimeoutException`, `httpx.NetworkError`, and `httpx.HTTPStatusError`, `reraise=True`.

**Notes:** PMC articles automatically set `open_access=True` and populate a PDF URL pointing to
the Europe PMC render endpoint.

## PubMedClient

**Base URL:** `https://eutils.ncbi.nlm.nih.gov/entrez/eutils`

**Auth:** Keyless with optional API key for higher rate limits (up to 10 req/s vs 3 req/s).

**Key env var:** `AGT_NCBI_API_KEY` (optional).

**Fields populated:** `title` (`<ArticleTitle>`), `abstract` (`<AbstractText>` nodes joined),
`authors` (from `<AuthorList>`), `doi` (`<ArticleId IdType="doi">`), `year` (`<PubDate/Year>`
or `MedlineDate` regex), `venue` (`<Journal/Title>`), `url`
(`https://pubmed.ncbi.nlm.nih.gov/{pmid}/`).

**Retry / timeout:** tenacity `AsyncRetrying` with exponential back-off on the `_request_text`
layer, retries on `httpx.TimeoutException`, `httpx.NetworkError`, and
`httpx.HTTPStatusError`, `reraise=True`.

**Notes:** Two-step retrieval: `esearch.fcgi` returns a list of PMIDs, then `efetch.fcgi`
returns full XML. PMC articles populate a PDF URL and set `open_access=True`.

## BaseSearchClient

**Base URL:** `https://api.base-search.net/cgi-bin/BaseHttpSearchInterface.fcgi`

**Auth:** Keyless. No API key required.

**Key env var:** None.

**Fields populated:** `title`, `abstract` (`<description>`), `authors` (`<creator>`), `doi`
(`<doi>`), `year` (`<year>`), `url` (`<url>`), `open_access` (detected from `<accessRights>`
containing "open" or "free").

**Retry / timeout:** tenacity `AsyncRetrying` with exponential back-off, retries on
`httpx.TimeoutException`, `httpx.NetworkError`, and `httpx.HTTPStatusError`, `reraise=True`.

**Notes:** BASE is the Bielefeld Academic Search Engine SRU interface. This is a search provider,
not a base class. Response is XML; the client parses `<record>` elements directly.

## SemanticScholarClient

**Base URL:** `https://api.semanticscholar.org/graph/v1`

**Auth:** Keyless path works at 1 req/s (enforced via internal semaphore + sleep). Optional API
key raises the quota.

**Key env var:** `AGT_SEMANTIC_SCHOLAR_API_KEY` (optional).

**Fields populated:** `title`, `abstract`, `authors` (from `authors[].name`), `doi`
(`externalIds.DOI`), `arxiv_id` (`externalIds.ArXiv`), `year`, `venue`, `citation_count`
(`citationCount`), `open_access` (`isOpenAccess`), `url`.

**Retry / timeout:** tenacity `AsyncRetrying` retries only on `httpx.TimeoutException` and
`httpx.NetworkError` (not `httpx.HTTPStatusError`). HTTP errors surface immediately. A 400 Bad
Request raises `SemanticScholarResponseError` directly without retrying. `reraise=True`.

**Notes:** Queries are preprocessed by `_clean_ss_query` to strip constraint phrases and
truncate to 10 words to avoid 400 errors. Rate-limit semaphore serialises concurrent calls.

## OpenCitationsClient

**Base URL:** `https://opencitations.net/index/coci/api/v1`

**Auth:** Keyless. No API key required.

**Key env var:** None.

**Fields populated:** `citation_count` (integer from `/citation-count/{doi}` endpoint).
This client does not implement `search()`; it is used exclusively for DOI-based citation-count
enrichment after primary retrieval.

**Retry / timeout:** tenacity `AsyncRetrying` with exponential back-off, retries on
`httpx.TimeoutException`, `httpx.NetworkError`, and `httpx.HTTPStatusError`, `reraise=True`.

**Notes:** Returns `None` when the DOI is unknown or the response list is empty. Returns `None`
(not 0) on a missing entry so callers can distinguish "not found" from "zero citations".

## CoreClient

**Base URL:** `https://api.core.ac.uk/v3`

**Auth:** API key required. The key is passed as a `Bearer` token in the `Authorization` header.

**Key env var:** `AGT_CORE_API_KEY` (required).

**Fields populated:** `title`, `abstract`, `authors` (from `authors[].name`), `doi`,
`year` (`yearPublished`), `url` (`downloadUrl`), `open_access` (`isOpenAccess`).

**Retry / timeout:** tenacity `AsyncRetrying` with exponential back-off, retries on
`httpx.TimeoutException`, `httpx.NetworkError`, and `httpx.HTTPStatusError`, `reraise=True`.

**Notes:** CORE indexes open-access full-text papers from repositories worldwide. The `downloadUrl`
field points to a direct PDF or landing page, making it particularly useful for full-text
retrieval pipelines.

## DimensionsClient

**Base URL:** `https://app.dimensions.ai/api`

**Auth:** API key required. Two-step: POST `/authenticate` with a `JWT {api_key}` header returns
a session token; subsequent DSL search requests use that token.

**Key env var:** `AGT_DIMENSIONS_KEY` (required).

**Fields populated:** `title`, `authors` (from `authors[].raw_name`), `doi`, `year`,
`citation_count` (`times_cited`). Abstract is not returned by the default DSL field set.

**Retry / timeout:** tenacity `AsyncRetrying` with exponential back-off on `_request_json`,
retries on `httpx.TimeoutException`, `httpx.NetworkError`, and `httpx.HTTPStatusError`,
`reraise=True`. The session token is cached after the first successful authentication.

**Notes:** The DSL query template uses `search publications in full_data for "{query}" return
publications[title+year+doi+times_cited+open_access+authors]`. Quote characters in the query
are stripped before embedding.

## GoogleScholarClient

**Base URL:** `https://serpapi.com/search.json`

**Auth:** API key required. The key is sent as the `api_key` query parameter.

**Key env var:** `AGT_SERPAPI_KEY` (required).

**Fields populated:** `title`, `abstract` (`snippet`), `authors`
(`publication_info.authors`), `year` (extracted from `publication_info.summary`), `url`
(`link`), `citation_count` (`inline_links.cited_by.total`).

**Retry / timeout:** tenacity `AsyncRetrying` with exponential back-off, retries on
`httpx.TimeoutException`, `httpx.NetworkError`, and `httpx.HTTPStatusError`, `reraise=True`.

**Notes:** SerpAPI is an unofficial Google Scholar proxy. It has strict rate limits and per-query
costs. The `num` parameter controls result count. This provider is optional and experimental;
results may differ from direct Google Scholar access.
