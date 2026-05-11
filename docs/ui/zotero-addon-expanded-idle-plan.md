# SciAgent — Expanded idle panel & agentic filter extraction

## What this document covers

Two connected features:

1. An expanded set of filter controls in the idle/compose panel, grounded
   in what systematic review researchers actually configure most.
2. Agentic filter extraction: as the user types a natural-language query,
   the backend parses structured constraints out of it and pre-fills the
   filter fields — highlighted and dismissable — before search fires.

Both features require backend changes as well as frontend changes.
Backend changes are listed per-filter below.

---

## Rationale for each new filter

Based on what systematic-review researchers configure most:

| Filter                       | Why it matters                                                                                                         | Backend support needed                                                                                                                                           |
| ---------------------------- | ---------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Year from / to               | Already exists                                                                                                         | Already in `SearchPlan.hard_filters`                                                                                                                             |
| Document type                | Preprints vs. journals is the #1 distinction in CS/AI; researchers explicitly include or exclude bioRxiv/arXiv results | New: `doc_type` field in `SearchPlan.hard_filters`; pushed to arXiv, Europe PMC, OpenAlex `type` filter                                                          |
| Open access                  | Already exists                                                                                                         | Already in `SearchPlan`                                                                                                                                          |
| Min citations                | Already exists                                                                                                         | Already in `SearchPlan`                                                                                                                                          |
| Language                     | Required for non-English corpora; NCBI/PubMed and OpenAlex support it natively                                         | New: `language` field; pushed to PubMed, OpenAlex, Europe PMC                                                                                                    |
| Exclude terms                | Already exists                                                                                                         | Already in `SearchPlan`                                                                                                                                          |
| Required terms (must appear) | Inclusion criteria in PRISMA reviews — paper must mention a concept                                                    | New: `require_terms` field; becomes mandatory `AND` in source queries                                                                                            |
| Venue quality                | Q1/Q2 journals, top conferences; increasingly requested in SLR workflows                                               | New: `venue_rank` field; checked post-merge using Scimago/CORE rank data (metadata only, no extra API call needed for papers that already have journal metadata) |
| Result count                 | Already configurable via env var; needs to be per-run                                                                  | New: `max_results` per-run override in `/run` request body                                                                                                       |
| PDF attachment               | Already P1 in roadmap                                                                                                  | Already planned (AGT-13); expose as per-run toggle                                                                                                               |
| Cross-encoder reranker       | Already feature-flagged                                                                                                | Expose `use_reranker` as per-run override                                                                                                                        |
| LLM query rewrite            | Already feature-flagged                                                                                                | Expose `use_rewrite` as per-run override                                                                                                                         |

---

## Backend changes required

### 1. Extend `SearchPlan.hard_filters`

In `src/agt/models.py`, add to `HardFilters` (or equivalent TypedDict):

```python
class HardFilters(TypedDict, total=False):
    min_year: int | None
    max_year: int | None
    open_access: Literal["any", "preferred", "required"]
    min_citations: int | None
    exclude_terms: list[str]
    # NEW FIELDS:
    require_terms: list[str]        # must appear in title/abstract
    doc_type: Literal["any", "journal", "preprint", "both", "conference"]
    language: str | None            # ISO 639-1, e.g. "en", "en,fr"
    venue_rank: Literal["any", "q1q2", "q1", "top-conf"]
```

### 2. Extend `/run` request body

In `src/agt/api/app.py`, the `RunRequest` model gains:

```python
class RunRequest(BaseModel):
    query: str
    collection_name: str = "SciAgent Results"
    thread_id: str | None = None
    overrides: RunOverrides | None = None

class RunOverrides(BaseModel):
    year_min: int | None = None
    year_max: int | None = None
    open_access: str | None = None
    doc_type: str | None = None          # NEW
    language: str | None = None          # NEW
    min_citations: str | None = None
    exclude_terms: list[str] = []
    require_terms: list[str] = []        # NEW
    venue_rank: str | None = None        # NEW
    sources: list[str] | None = None
    max_results: int | None = None       # NEW (per-run override)
    use_reranker: bool | None = None     # NEW (per-run override)
    use_rewrite: bool | None = None      # NEW (per-run override)
    pdf_attachment: bool | None = None   # NEW (per-run override)
```

### 3. Push new filters to source adapters

#### `doc_type` filter

| Source           | Pushdown mechanism                                         |
| ---------------- | ---------------------------------------------------------- |
| arXiv            | Already preprint-only; if `doc_type="journal"`, skip arXiv |
| OpenAlex         | `filter=type:journal-article` or `type:preprint`           |
| Europe PMC       | `resulttype=core` (peer-reviewed) or `resulttype=preprint` |
| PubMed           | `[pt]` publication type filter                             |
| Crossref         | `filter=type:journal-article`                              |
| Semantic Scholar | `fieldsOfStudy` + post-filter on `publicationTypes`        |

In `src/agt/tools/search_papers.py`, before fanning out to adapters:

```python
def should_query_source(source: str, doc_type: str) -> bool:
    if doc_type == "journal" and source == "arxiv":
        return False          # arXiv is preprint-only
    if doc_type == "preprint" and source in ("crossref", "pubmed"):
        return False          # these are journal-only effectively
    return True
```

#### `require_terms` filter

Applied at two levels:

1. Injected into the source query as mandatory AND terms (where supported)
2. Post-merge filter: any paper whose title + abstract does not contain
   at least one of the required terms is removed before ranking.

```python
def apply_require_terms(papers: list[NormalizedPaper], require_terms: list[str]) -> list[NormalizedPaper]:
    if not require_terms:
        return papers
    def matches(p: NormalizedPaper) -> bool:
        text = ((p.title or "") + " " + (p.abstract or "")).lower()
        return all(t.lower() in text for t in require_terms)
    return [p for p in papers if matches(p)]
```

#### `language` filter

Pushed to PubMed (`[la]`), OpenAlex (`filter=language:`), Europe PMC.
Applied post-merge for sources that don't support it natively (Crossref, Semantic Scholar).

#### `venue_rank` filter

Applied post-merge only — no source supports this as a query parameter.
Use the `journal` / `venue` metadata already on `NormalizedPaper` and
check against a bundled SCIMAGO rank lookup (a ~500KB JSON mapping ISSN → rank).

```python
# src/agt/tools/venue_rank.py (new file)
import json, importlib.resources

_RANKS: dict[str, str] = {}  # ISSN -> "Q1"|"Q2"|"Q3"|"Q4"

def load_ranks():
    global _RANKS
    with importlib.resources.open_text("agt.data", "scimago_ranks.json") as f:
        _RANKS = json.load(f)

def filter_by_venue_rank(papers: list[NormalizedPaper], rank: str) -> list[NormalizedPaper]:
    if rank == "any" or not _RANKS:
        return papers
    allowed = {"q1q2": {"Q1","Q2"}, "q1": {"Q1"}, "top-conf": {"A*","A"}}.get(rank, set())
    def passes(p: NormalizedPaper) -> bool:
        issn = getattr(p, "journal_issn", None)
        if not issn:
            return True   # keep if we can't verify (benefit of the doubt)
        return _RANKS.get(issn, "Q4") in allowed
    return [p for p in papers if passes(p)]
```

### 4. New endpoint: `POST /parse-query`

This is the backend half of agentic extraction. Called while the user
is typing (debounced, 600ms after last keystroke).

```python
@app.post("/parse-query")
async def parse_query(body: ParseQueryRequest) -> ParseQueryResponse:
    """
    Lightweight LLM call that extracts structured filters from a
    natural-language query string. Returns parsed fields + the
    cleaned topic query (original minus the constraint phrases).
    Does NOT run search. Cheap: single LLM call with a short prompt.
    """
    ...

class ParseQueryRequest(BaseModel):
    query: str

class ParseQueryResponse(BaseModel):
    topic_query: str              # query with constraint phrases removed
    extracted: ExtractedFilters
    extraction_notes: list[str]   # human-readable explanation per extracted field

class ExtractedFilters(BaseModel):
    min_year: int | None = None
    max_year: int | None = None
    open_access: str | None = None
    doc_type: str | None = None
    exclude_terms: list[str] = []
    require_terms: list[str] = []
    min_citations: str | None = None
```

#### LLM prompt for `/parse-query`

```python
PARSE_PROMPT = """
You are a filter extractor for an academic search tool.
Given a natural language research query, extract structured search constraints.
Return ONLY valid JSON, no explanation, no markdown.

Schema:
{
  "topic_query": "<the query with constraint phrases removed>",
  "extracted": {
    "min_year": <integer or null>,
    "max_year": <integer or null>,
    "open_access": <"any"|"preferred"|"required" or null>,
    "doc_type": <"any"|"journal"|"preprint"|"both"|"conference" or null>,
    "exclude_terms": [<strings>],
    "require_terms": [<strings>],
    "min_citations": <"any"|"cited"|"influential"|"game" or null>
  },
  "extraction_notes": [<one short phrase per extracted field explaining what phrase triggered it>]
}

Rules:
- "not older than 2023" → min_year: 2023
- "between 2022 and 2024" → min_year: 2022, max_year: 2024
- "can be not published", "preprints ok", "including preprints" → doc_type: "both"
- "preprints only", "arxiv only" → doc_type: "preprint"
- "peer reviewed only", "no preprints", "journal articles only" → doc_type: "journal"
- "open access only" → open_access: "required"
- "no X", "excluding X", "not about X" → exclude_terms: ["X"]
- "highly cited", "most cited" → min_citations: "influential"
- "game changing", "seminal" → min_citations: "game"
- If nothing is extractable, return empty extracted object and original query as topic_query.

Query: {query}
"""
```

Cost estimate: ~150 input tokens + ~100 output tokens per parse call.
At typical LLM rates this is < $0.001 per call. Cache by query hash.

---

## Frontend changes

### Idle panel layout (full control list)

Replace the previous 4-control 2×2 grid with:

```
Row 1 (2 col): Year from | Year to
Row 2 (2 col): Open access | Document type
Row 3 (2 col): Min citations | Language
Row 4 (1 col): Exclude terms
Row 5 (1 col): Required terms (must appear)
Row 6 (2 col): Venue quality | Result count
─── toggles ───
Toggle: PDF attachment
Toggle: Re-rank with cross-encoder
Toggle: LLM query rewrite
─── sources ───
Source chips
─── collection ───
Collection name input
Search button
```

Total height increase: approximately 120px.
Recommended window default: `width=440, height=780` (was 680).
Window is resizable so power users can expand further.

### Agentic extraction flow

#### Timing and triggering

```typescript
// In sciagentWindow.ts
const DEBOUNCE_MS = 600;
let debounceTimer: ReturnType<typeof setTimeout> | null = null;

queryInput.addEventListener("input", () => {
  const q = queryInput.value.trim();
  updateSearchButton(q);

  if (debounceTimer) clearTimeout(debounceTimer);
  if (q.length < 15) {
    hideBanner();
    return;
  } // too short to parse

  debounceTimer = setTimeout(() => parseQueryAndExtract(q), DEBOUNCE_MS);
});
```

#### Calling the backend

```typescript
async function parseQueryAndExtract(query: string) {
  // Cache by query hash to avoid re-parsing identical strings
  const cacheKey = simpleHash(query);
  if (parseCache.has(cacheKey)) {
    applyExtraction(parseCache.get(cacheKey)!);
    return;
  }

  try {
    const res = await backendFetch("/parse-query", {
      method: "POST",
      body: JSON.stringify({ query }),
    });
    const parsed: ParseQueryResponse = await res.json();
    parseCache.set(cacheKey, parsed);
    applyExtraction(parsed);
  } catch {
    // Silent fail — user can fill filters manually
  }
}
```

#### Applying extractions to the form

```typescript
function applyExtraction(parsed: ParseQueryResponse) {
  const { extracted, extraction_notes } = parsed;
  const applied: AppliedExtraction[] = [];

  if (extracted.min_year) {
    setField("f-ymin", String(extracted.min_year));
    highlightField("fb-ymin");
    applied.push({
      field: "f-ymin",
      fb: "fb-ymin",
      label: `year from: ${extracted.min_year}`,
      note: extraction_notes[applied.length] ?? "",
    });
  }
  if (extracted.max_year) {
    setField("f-ymax", String(extracted.max_year));
    highlightField("fb-ymax");
    applied.push({
      field: "f-ymax",
      fb: "fb-ymax",
      label: `year to: ${extracted.max_year}`,
      note: extraction_notes[applied.length] ?? "",
    });
  }
  if (extracted.doc_type && extracted.doc_type !== "any") {
    setField("f-dtype", extracted.doc_type);
    highlightField("fb-dtype");
    applied.push({
      field: "f-dtype",
      fb: "fb-dtype",
      label: docTypeLabel(extracted.doc_type),
      note: extraction_notes[applied.length] ?? "",
    });
  }
  if (extracted.open_access && extracted.open_access !== "any") {
    setField("f-oa", extracted.open_access);
    highlightField("fb-oa");
    applied.push({
      field: "f-oa",
      fb: "fb-oa",
      label: `open access: ${extracted.open_access}`,
      note: extraction_notes[applied.length] ?? "",
    });
  }
  if (extracted.exclude_terms.length) {
    setField("f-excl", extracted.exclude_terms.join(", "));
    highlightField("fb-excl");
    applied.push({
      field: "f-excl",
      fb: "fb-excl",
      label: `exclude: ${extracted.exclude_terms.join(", ")}`,
      note: extraction_notes[applied.length] ?? "",
    });
  }
  if (extracted.require_terms.length) {
    setField("f-req", extracted.require_terms.join(", "));
    highlightField("fb-req");
    applied.push({
      field: "f-req",
      fb: "fb-req",
      label: `must include: ${extracted.require_terms.join(", ")}`,
      note: extraction_notes[applied.length] ?? "",
    });
  }
  if (extracted.min_citations && extracted.min_citations !== "any") {
    setField("f-cit", extracted.min_citations);
    highlightField("fb-cit");
    applied.push({
      field: "f-cit",
      fb: "fb-cit",
      label: `citations: ${citLabel(extracted.min_citations)}`,
      note: extraction_notes[applied.length] ?? "",
    });
  }

  if (applied.length > 0) {
    renderExtractionBanner(applied);
  }
}
```

#### Extraction banner

The banner sits between the query input and the filter section.
Each extracted value gets a dismissable tag. Dismissing a tag:

- Removes the highlight from the corresponding filter box
- Resets that field to its default value
- The user's manual edit of the field value is then the active value

Key rules:

- Banner only appears if at least 1 field was extracted.
- After the user manually edits a highlighted field, its highlight turns
  from green to amber (indicating "extracted but overridden").
- Clicking "dismiss all" hides the banner but does not reset the fields
  — the extracted values stay, user just hides the visual annotation.

```typescript
function watchForManualOverride(fieldId: string, fbId: string) {
  const input = doc.getElementById(fieldId);
  const fb = doc.getElementById(fbId);
  if (!input || !fb) return;
  input.addEventListener(
    "input",
    () => {
      // User typed into an extracted field — change highlight to "overridden"
      fb.classList.remove("highlight");
      fb.classList.add("highlight-override"); // amber style
    },
    { once: true },
  );
}
```

CSS for override state:

```css
.fbox.highlight-override {
  border-color: var(--agt-amber);
  background: var(--agt-amber-dim);
}
.fbox.highlight-override .flabel {
  color: var(--agt-amber);
}
.fbox.highlight-override .finput,
.fbox.highlight-override .fselect {
  color: var(--agt-amber);
}
```

---

## What does NOT go in the idle panel

These remain backend-only (env/config) and are NOT exposed per-run:

- API keys for LLM providers and search sources
- Rate limits per source
- Cost cap per workflow
- LangGraph checkpoint backend
- Log level

These belong in the Zotero **Preferences panel** (ZAP-9 — already planned),
not the search compose panel. The compose panel is for search-time decisions,
not permanent configuration.

---

## Updated `/health` capability response

The add-on reads capabilities on startup to know which controls to enable.
Add the new fields:

```python
class CapabilityResponse(BaseModel):
    contract_version: str
    sources: list[SourceCapability]
    features: FeatureFlags
    filter_support: FilterSupport   # NEW

class FilterSupport(BaseModel):
    doc_type: bool = True
    language: bool = True
    require_terms: bool = True
    venue_rank: bool = True         # False until scimago_ranks.json ships
    parse_query: bool = True        # False if LLM not configured

class FeatureFlags(BaseModel):
    pdf_attachment: bool
    reranker: bool
    query_rewrite: bool
```

The add-on uses `filter_support.venue_rank` to show/hide the venue
quality control, and `filter_support.parse_query` to enable/disable
the agentic extraction call. If the backend doesn't support it yet,
the feature is silently absent — no error shown.

---

## Acceptance criteria

**Idle panel:**

- [ ] All 8 filter controls visible in the compose panel
- [ ] Toggles for PDF, reranker, LLM rewrite work and send per-run overrides
- [ ] Source chips reflect backend capability metadata (keyed sources shown as off/greyed)
- [ ] Venue quality control hidden if `filter_support.venue_rank = false`
- [ ] Window default height updated to 780px

**Agentic extraction:**

- [ ] `/parse-query` endpoint exists, returns `ExtractedFilters` + `extraction_notes`
- [ ] Extraction banner appears within 700ms of user stopping typing (600ms debounce + ~100ms round trip)
- [ ] Each extracted tag is dismissable — dismissing resets that field to default
- [ ] Manually editing an extracted field changes highlight from green to amber
- [ ] "Dismiss all" hides banner, keeps values
- [ ] No extraction call fired if query < 15 characters
- [ ] Parse results cached per query string — repeated text doesn't re-call backend
- [ ] If backend `/parse-query` fails or is unavailable, silent fail — user fills manually
- [ ] All three example phrases extract correctly:
  - "not older than 2023" → `min_year: 2023`
  - "can be not published" / "preprints ok" → `doc_type: "both"`
  - "open access only" → `open_access: "required"`
  - "no healthcare" → `exclude_terms: ["healthcare"]`
  - "highly cited" → `min_citations: "influential"`
  - "between 2022 and 2024" → `min_year: 2022, max_year: 2024`

**Backend:**

- [ ] `doc_type` pushed to arXiv (skip if "journal"), OpenAlex, Europe PMC
- [ ] `require_terms` applied post-merge as hard filter
- [ ] `language` pushed to PubMed, OpenAlex, Europe PMC; post-merge elsewhere
- [ ] `venue_rank` applied post-merge using bundled SCIMAGO data
- [ ] All new fields appear in `SearchPlan` and are shown in the plan pill (State 2)
- [ ] All new overrides accepted by `/run` and merged with env defaults
- [ ] New `filter_support` block in `/health` response
