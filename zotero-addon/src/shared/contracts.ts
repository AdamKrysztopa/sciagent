export type RunStatus = "awaiting_approval" | "completed" | "rejected" | "failed";

export const REQUIRED_API_CONTRACT_VERSION = "2026-05";

export interface PreflightStatus {
  ok: boolean;
  can_read?: boolean;
  can_write?: boolean;
  key_valid?: boolean;
  message?: string;
  library_name?: string | null;
}

export interface HealthResponse {
  ok: boolean;
  message: string;
  preflight: PreflightStatus;
  provider: string;
  fallback_provider: string | null;
  api_contract_version?: string;
}

export type ContractCompatibility = "compatible" | "missing" | "mismatch";

export function validateContractVersion(response: HealthResponse | null): ContractCompatibility {
  if (response === null) {
    return "missing";
  }
  if (response.api_contract_version === undefined) {
    return "missing";
  }
  if (response.api_contract_version !== REQUIRED_API_CONTRACT_VERSION) {
    return "mismatch";
  }
  return "compatible";
}

export interface HardFilters {
  min_year: number | null;
  max_year: number | null;
  min_citations: number;
  max_citations: number | null;
  open_access_only: boolean;
  include_keywords: string[];
  exclude_keywords: string[];
  author_ids?: string[];
  author_names?: string[];
  venue_ids?: string[];
}

export interface ResolvedVenue {
  name: string;
  openalex_id: string | null;
  issn: string | null;
}

export interface ResolvedAuthor {
  name: string;
  openalex_id: string | null;
  orcid: string | null;
  s2_author_id: string | null;
}

export interface SoftPreferences {
  require_positive_community_perception: boolean;
  min_semantic_score: number;
}

export interface SourceCapability {
  name: string;
  tier: "primary" | "fallback";
  enabled: boolean;
  supports_year_filter: boolean;
  supports_open_access_filter: boolean;
}

export interface SearchPlan {
  original_query: string;
  topic_query: string;
  rewritten_queries: string[];
  hard_filters: HardFilters;
  soft_preferences: SoftPreferences;
  source_policy: SourceCapability[];
  filters_pushed_down: Record<string, string[]>;
  filters_enforced_post_merge: string[];
}

export interface FilterEditContract {
  original_query: string;
  hard_filters: HardFilters;
  soft_preferences: SoftPreferences;
  result_limit: number;
  authors?: ResolvedAuthor[];
  venues?: ResolvedVenue[];
  seed_dois?: string[];
}

export interface NormalizedAuthor {
  name: string;
  family: string | null;
  given: string | null;
  orcid: string | null;
  openalex_id: string | null;
  s2_author_id: string | null;
  affiliation: string | null;
  source: string;
}

export interface FieldConflictValue {
  provider: string;
  value: unknown;
}

export interface FieldConflict {
  field: string;
  values: FieldConflictValue[];
}

export interface ProviderFieldSupport {
  [field: string]: "full" | "shallow" | "none";
}

export interface ProviderInfo {
  name: string;
  requires_key: boolean;
  key_env_var: string | null;
  key_upgrade_hint: string | null;
  fields: ProviderFieldSupport;
  notes: string;
  health: {
    status: "available" | "shallow" | "disabled" | "missing_key" | "failed" | "rate_limited";
    reason: string;
    last_ok_at: number | null;
    last_error_at: number | null;
    consecutive_failures: number;
    retry_after: number | null;
  };
}

// SCI-0301
export type LibraryStatus = "new" | "in_library" | "possible_duplicate";

// SCI-0401
export type WatchStatus = "new" | "seen";

export interface NormalizedPaper {
  title: string;
  year: number | null;
  doi: string | null;
  arxiv_id: string | null;
  abstract: string | null;
  authors: (NormalizedAuthor | string)[];
  sources?: string[];
  conflicts?: FieldConflict[];
  oa_url?: string | null;
  url: string | null;
  pdf_url: string | null;
  source: string;
  index: number | null;
  semantic_score: number;
  citation_count: number;
  influential_citation_count: number;
  open_access: boolean;
  summary: string | null;
  score: number;
  explanation: string | null;
  library_status?: LibraryStatus | null;
  watch_status?: WatchStatus | null;
  venue: string | null;
  item_type: "journal_article" | "preprint" | "conference_paper" | "book_chapter" | "other" | null;
  volume: string | null;
  issue: string | null;
  pages: string | null;
  citation_relation?: "references" | "cited_by" | null;
  missing_reasons?: Record<string, string>;
}

export type SourceTerminalState =
  | "queried"
  | "skipped_no_key"
  | "skipped_disabled"
  | "rate_limited"
  | "zero_results"
  | "failed";

export interface SearchMetadata {
  original_query: string;
  rewritten_query: string | null;
  regex_query: string;
  sources_used: string[];
  sources_failed: string[];
  source_states: Record<string, SourceTerminalState>;
  mode: "llm_rewrite" | "regex";
  retry_count: number;
  total_fetched: number;
  total_after_filter: number;
  source_timings: Record<string, number>;
  search_plan: SearchPlan | null;
  baseline_mode?: boolean;
}

export interface CollectionResult {
  key: string;
  name: string;
  parent_key: string | null;
  reused: boolean;
}

export interface ItemWriteOutcome {
  index: number;
  title: string;
  status: "created" | "unchanged" | "failed";
  item_key: string | null;
  reason: string | null;
  duplicate_strategy: "doi" | "title_author_hash" | null;
  retry_safe: boolean;
}

export interface WriteResult {
  created: number;
  unchanged: number;
  failed: number;
  collection: CollectionResult;
  outcomes: ItemWriteOutcome[];
  retry_safe_failures: number;
}

export interface AgentStateSnapshot {
  request_id: string;
  thread_id: string;
  messages: string[];
  papers: NormalizedPaper[];
  collection_name: string | null;
  approved: boolean;
  decision: "approved" | "rejected" | "pending";
  phase: "search_complete" | "awaiting_approval" | "completed" | "rejected" | "failed";
  selected_indices: number[];
  preflight: PreflightStatus;
  trace_spans: Array<Record<string, unknown>>;
  write_result: WriteResult | null;
  search_metadata: SearchMetadata | null;
}

export interface RunRequest {
  query: string;
  collection_name: string;
  thread_id?: string;
  filter_edit?: FilterEditContract;
  search_depth?: "quick" | "balanced" | "deep";
  force_refresh?: boolean;
}

export interface ResumeRequest {
  run_id: string;
  approved: boolean;
  collection_name?: string;
  selected_indices?: number[];
  /** When true the backend skips pyzotero write and returns approved_papers for native JS write. */
  native_write?: boolean;
  // SCI-0302
  enable_pdf_imports?: boolean;
}

export interface RunAcceptedResponse {
  run_id: string;
  thread_id: string;
  status: RunStatus;
  /** Populated when ResumeRequest.native_write=true so the add-on can perform ZAP-6/7/8. */
  approved_papers?: NormalizedPaper[];
}

export interface CapabilitiesResponse {
  api_contract_version: string;
  source_policy: SourceCapability[];
  filter_support: Record<string, string[]>;
  pdf_import_supported: boolean;
  provider_availability: Record<string, boolean>;
  active_provider: string;
}

export interface CorrectQueryResponse {
  original: string;
  corrected: string;
  changed: boolean;
}

export interface ExtractKeywordsResponse {
  include_keywords: string[];
  exclude_keywords: string[];
  collection_name: string | null;
  min_year: number | null;
  max_year: number | null;
  min_citations: number | null;
  max_citations: number | null;
  open_access_only: boolean;
}

// SCI-0303
export interface DoctorIssue {
  item_key: string;
  title: string;
  issue_types: Array<"missing_doi" | "missing_abstract" | "missing_pdf" | "duplicate">;
  duplicate_of: string | null;
}

export interface DoctorReport {
  collection_name: string;
  total_items: number;
  issues: DoctorIssue[];
  duplicate_pairs: [string, string][];
}

// SCI-0304
export interface GapFinderResponse {
  reasoning: string;
  papers: NormalizedPaper[];
}

// SCI-0401/0402
export interface Watch {
  id: string;
  name: string;
  query: string;
  collection_name: string | null;
  created_at: string;
  last_run_at: string | null;
  seen_count: number;
  filter_edit: FilterEditContract | null;
}

export interface WatchRerunResponse {
  watch_id: string;
  run_id: string;
  thread_id: string;
  status: RunStatus;
  new_count: number;
  total_count: number;
}

export interface StatusResponse {
  run_id: string;
  thread_id: string;
  status: RunStatus;
  state: AgentStateSnapshot | null;
  error: string | null;
}

export interface SourceBuckets {
  configured: string[];
  used: string[];
  failed: string[];
  skipped: string[];
  unavailable_optional: string[];
}

export const DEFAULT_HARD_FILTERS: HardFilters = {
  min_year: null,
  max_year: null,
  min_citations: 0,
  max_citations: null,
  open_access_only: false,
  include_keywords: [],
  exclude_keywords: [],
};

export const DEFAULT_SOFT_PREFERENCES: SoftPreferences = {
  require_positive_community_perception: false,
  min_semantic_score: 0,
};

const OPTIONAL_SOURCES = ["core", "dimensions", "google_scholar"] as const;

export function buildDefaultFilterEdit(
  minYear: number | null = null,
  maxYear: number | null = null,
  minCitations = 0,
  openAccessOnly = false,
): FilterEditContract {
  return {
    original_query: "",
    hard_filters: {
      ...DEFAULT_HARD_FILTERS,
      min_year: minYear,
      max_year: maxYear,
      min_citations: minCitations,
      open_access_only: openAccessOnly,
    },
    soft_preferences: { ...DEFAULT_SOFT_PREFERENCES },
    result_limit: 10,
    seed_dois: [],
  };
}

export function filterEditFromSearchPlan(
  originalQuery: string,
  searchPlan: SearchPlan,
  resultLimit: number,
): FilterEditContract {
  return {
    original_query: originalQuery,
    hard_filters: {
      ...searchPlan.hard_filters,
      include_keywords: [...searchPlan.hard_filters.include_keywords],
      exclude_keywords: [...searchPlan.hard_filters.exclude_keywords],
    },
    soft_preferences: { ...searchPlan.soft_preferences },
    result_limit: resultLimit,
    seed_dois: [],
  };
}

export function getPaperIndex(paper: NormalizedPaper, fallbackIndex: number): number {
  return typeof paper.index === "number" ? paper.index : fallbackIndex;
}

export function getAuthorName(author: NormalizedAuthor | string): string {
  if (typeof author === "string") {
    return author;
  }
  return author.name;
}

export function getAuthorId(author: NormalizedAuthor | string): string | null {
  if (typeof author === "string") {
    return null;
  }
  return author.openalex_id ?? author.orcid ?? author.s2_author_id ?? null;
}

export function keywordListToText(values: readonly string[]): string {
  return values.join(", ");
}

export function parseKeywordList(value: string): string[] {
  return value
    .split(",")
    .map((keyword) => keyword.trim())
    .filter((keyword) => keyword.length > 0);
}

export function uniqueSortedIndices(values: readonly number[]): number[] {
  return [...new Set(values)].sort((left, right) => left - right);
}

// P8.10-B: Provider key validation
export interface KeyValidateRequest {
  provider: string;
  api_key: string;
}

export interface KeyValidateResponse {
  provider: string;
  valid: boolean;
  error: string | null;
}

export interface UserMessage {
  id: string;
  type: "info" | "warning" | "critical";
  text: string;
  created_at: number;
}

export const VALIDATABLE_PROVIDERS: readonly string[] = [
  "semantic_scholar",
  "ncbi",
  "core",
  "serpapi",
  "dimensions",
] as const;

export function buildSourceBuckets(searchMetadata: SearchMetadata | null): SourceBuckets | null {
  if (searchMetadata === null || searchMetadata.search_plan === null) {
    return null;
  }

  const configured = searchMetadata.search_plan.source_policy.map((source) => source.name);
  const used = [...searchMetadata.sources_used];
  const failed = [...searchMetadata.sources_failed];
  const skipped = configured.filter(
    (source) => !used.includes(source) && !failed.includes(source),
  );
  const unavailableOptional = OPTIONAL_SOURCES.filter(
    (source) => !configured.includes(source),
  );

  return {
    configured,
    used,
    failed,
    skipped,
    unavailable_optional: unavailableOptional,
  };
}
