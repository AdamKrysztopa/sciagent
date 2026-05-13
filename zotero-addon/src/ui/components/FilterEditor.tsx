import { useEffect, useEffectEvent, useState } from "react";
import type { FilterEditContract, NormalizedAuthor, ResolvedAuthor, ResolvedVenue, SearchPlan } from "../../shared/contracts";
import { keywordListToText, parseKeywordList } from "../../shared/contracts";

// ── AuthorChipInput ───────────────────────────────────────────────────────────

interface AuthorChipInputProps {
  authors: ResolvedAuthor[];
  disabled: boolean;
  onChange(next: ResolvedAuthor[]): void;
  onSuggest(q: string): Promise<NormalizedAuthor[]>;
}

function AuthorChipInput({ authors, disabled, onChange, onSuggest }: AuthorChipInputProps) {
  const [inputValue, setInputValue] = useState("");
  const [suggestions, setSuggestions] = useState<NormalizedAuthor[]>([]);

  const doSuggest = useEffectEvent(async (q: string) => {
    try {
      const results = await onSuggest(q);
      setSuggestions(results);
    } catch {
      setSuggestions([]);
    }
  });

  useEffect(() => {
    const trimmed = inputValue.trim();
    if (trimmed.length < 2) {
      setSuggestions([]);
      return;
    }
    const timer = setTimeout(() => { void doSuggest(trimmed); }, 200);
    return () => clearTimeout(timer);
  }, [inputValue]);

  const addAuthor = (author: NormalizedAuthor) => {
    const resolved: ResolvedAuthor = {
      name: author.name,
      openalex_id: author.openalex_id,
      orcid: author.orcid,
      s2_author_id: author.s2_author_id,
    };
    const alreadyAdded = authors.some(
      (a) => a.name === resolved.name && a.openalex_id === resolved.openalex_id,
    );
    if (!alreadyAdded) {
      onChange([...authors, resolved]);
    }
    setInputValue("");
    setSuggestions([]);
  };

  const removeAuthor = (index: number) => {
    onChange(authors.filter((_, i) => i !== index));
  };

  return (
    <div className="agt-author-input">
      {authors.length > 0 ? (
        <div className="agt-chip-list">
          {authors.map((author, i) => (
            <span className="agt-chip agt-chip--removable" key={`${author.name}:${author.openalex_id ?? author.orcid ?? String(i)}`}>
              {author.name}
              {author.openalex_id !== null ? <span className="agt-chip-badge">OA</span> : null}
              {author.orcid !== null ? <span className="agt-chip-badge">ORC</span> : null}
              <button
                aria-label={`Remove ${author.name}`}
                className="agt-chip-remove"
                disabled={disabled}
                onClick={() => removeAuthor(i)}
                type="button"
              >
                ×
              </button>
            </span>
          ))}
        </div>
      ) : null}
      <div className="agt-suggest-wrap">
        <input
          className="agt-input"
          disabled={disabled}
          onChange={(event) => setInputValue(event.target.value)}
          placeholder="Type author name…"
          type="text"
          value={inputValue}
        />
        {suggestions.length > 0 ? (
          <ul className="agt-suggest-list">
            {suggestions.map((s, i) => (
              <li key={s.openalex_id ?? s.orcid ?? `${s.name}-${String(i)}`}>
                <button
                  className="agt-suggest-item"
                  onClick={() => addAuthor(s)}
                  type="button"
                >
                  <span className="agt-suggest-item__name">{s.name}</span>
                  {s.affiliation !== null ? (
                    <span className="agt-suggest-item__affil">{s.affiliation}</span>
                  ) : null}
                  {s.openalex_id !== null ? <span className="agt-chip-badge">OA</span> : null}
                  {s.orcid !== null ? <span className="agt-chip-badge">ORC</span> : null}
                </button>
              </li>
            ))}
          </ul>
        ) : null}
      </div>
    </div>
  );
}

// ── VenueChipInput ────────────────────────────────────────────────────────────

interface VenueChipInputProps {
  venues: ResolvedVenue[];
  disabled: boolean;
  onChange(next: ResolvedVenue[]): void;
  onSuggest(q: string): Promise<ResolvedVenue[]>;
}

function VenueChipInput({ venues, disabled, onChange, onSuggest }: VenueChipInputProps) {
  const [inputValue, setInputValue] = useState("");
  const [suggestions, setSuggestions] = useState<ResolvedVenue[]>([]);

  const doSuggest = useEffectEvent(async (q: string) => {
    try {
      const results = await onSuggest(q);
      setSuggestions(results);
    } catch {
      setSuggestions([]);
    }
  });

  useEffect(() => {
    const trimmed = inputValue.trim();
    if (trimmed.length < 2) {
      setSuggestions([]);
      return;
    }
    const timer = setTimeout(() => { void doSuggest(trimmed); }, 200);
    return () => clearTimeout(timer);
  }, [inputValue]);

  const addVenue = (venue: ResolvedVenue) => {
    const alreadyAdded = venues.some(
      (v) => v.name === venue.name && v.openalex_id === venue.openalex_id,
    );
    if (!alreadyAdded) {
      onChange([...venues, venue]);
    }
    setInputValue("");
    setSuggestions([]);
  };

  const removeVenue = (index: number) => {
    onChange(venues.filter((_, i) => i !== index));
  };

  return (
    <div className="agt-author-input">
      {venues.length > 0 ? (
        <div className="agt-chip-list">
          {venues.map((venue, i) => (
            <span className="agt-chip agt-chip--removable" key={`${venue.name}:${venue.openalex_id ?? venue.issn ?? String(i)}`}>
              {venue.name}
              {venue.openalex_id !== null ? <span className="agt-chip-badge">OA</span> : null}
              {venue.issn !== null ? <span className="agt-chip-badge">ISSN</span> : null}
              <button
                aria-label={`Remove ${venue.name}`}
                className="agt-chip-remove"
                disabled={disabled}
                onClick={() => removeVenue(i)}
                type="button"
              >
                ×
              </button>
            </span>
          ))}
        </div>
      ) : null}
      <div className="agt-suggest-wrap">
        <input
          className="agt-input"
          disabled={disabled}
          onChange={(event) => setInputValue(event.target.value)}
          placeholder="Type venue or journal name…"
          type="text"
          value={inputValue}
        />
        {suggestions.length > 0 ? (
          <ul className="agt-suggest-list">
            {suggestions.map((s, i) => (
              <li key={s.openalex_id ?? s.issn ?? `${s.name}-${String(i)}`}>
                <button
                  className="agt-suggest-item"
                  onClick={() => addVenue(s)}
                  type="button"
                >
                  <span className="agt-suggest-item__name">{s.name}</span>
                  {s.openalex_id !== null ? <span className="agt-chip-badge">OA</span> : null}
                  {s.issn !== null ? <span className="agt-chip-badge">ISSN</span> : null}
                </button>
              </li>
            ))}
          </ul>
        ) : null}
      </div>
    </div>
  );
}

// ── FilterEditor ──────────────────────────────────────────────────────────────

interface FilterEditorProps {
  disabled: boolean;
  filterDraft: FilterEditContract | null;
  onChange(nextDraft: FilterEditContract): void;
  onReset(): void;
  onSuggestAuthors?: (q: string) => Promise<NormalizedAuthor[]>;
  onSuggestVenues?: (q: string) => Promise<ResolvedVenue[]>;
  searchPlan: SearchPlan | null;
}

export function FilterEditor({
  disabled,
  filterDraft,
  onChange,
  onReset,
  onSuggestAuthors,
  onSuggestVenues,
  searchPlan,
}: FilterEditorProps) {
  if (filterDraft === null) {
    return (
      <section className="agt-card agt-card--soft">
        <div className="agt-section-heading">
          <h2>Pre-Search Filters</h2>
        </div>
        <p className="agt-empty-state">Loading saved filter defaults…</p>
      </section>
    );
  }

  const isPreSearch = searchPlan === null;
  const sectionHeading = isPreSearch ? "Pre-Search Filters" : "Parsed Filters";
  const hint = isPreSearch
    ? "Set deterministic hard filters before search. These are sent with the initial /run request. The backend applies them before semantic rewrite and candidate generation."
    : "These controls mirror the backend FilterEditContract. Re-running search sends the edited payload back through /run.";

  const update = (nextDraft: FilterEditContract) => {
    onChange(nextDraft);
  };

  const updateHardFilters = (nextValues: Partial<FilterEditContract["hard_filters"]>) => {
    update({
      ...filterDraft,
      hard_filters: {
        ...filterDraft.hard_filters,
        ...nextValues,
      },
    });
  };

  const updateSoftPreferences = (
    nextValues: Partial<FilterEditContract["soft_preferences"]>,
  ) => {
    update({
      ...filterDraft,
      soft_preferences: {
        ...filterDraft.soft_preferences,
        ...nextValues,
      },
    });
  };

  return (
    <section className="agt-card">
      <div className="agt-section-heading">
        <h2>{sectionHeading}</h2>
        <button className="agt-button agt-button--ghost" disabled={disabled || searchPlan === null} onClick={onReset} type="button">
          Reset To Parsed Plan
        </button>
      </div>
      <p className="agt-hint">{hint}</p>
      <div className="agt-grid--compact">
        <label className="agt-field">
          <span>Result Limit</span>
          <input
            className="agt-number"
            disabled={disabled}
            max={50}
            min={1}
            onChange={(event) => {
              const value = Number(event.target.value);
              update({ ...filterDraft, result_limit: Number.isNaN(value) ? 10 : value });
            }}
            type="number"
            value={filterDraft.result_limit}
          />
        </label>
        <label className="agt-field">
          <span>Min Semantic Score</span>
          <input
            className="agt-number"
            disabled={disabled}
            max={1}
            min={0}
            onChange={(event) => {
              const value = Number(event.target.value);
              updateSoftPreferences({ min_semantic_score: Number.isNaN(value) ? 0 : value });
            }}
            step="0.05"
            type="number"
            value={filterDraft.soft_preferences.min_semantic_score}
          />
        </label>
      </div>
      <div className="agt-grid">
        <label className="agt-field">
          <span>Min Year</span>
          <input
            className="agt-number"
            disabled={disabled}
            max={2100}
            min={1900}
            onChange={(event) => {
              updateHardFilters({
                min_year: event.target.value === "" ? null : Number(event.target.value),
              });
            }}
            type="number"
            value={filterDraft.hard_filters.min_year ?? ""}
          />
        </label>
        <label className="agt-field">
          <span>Max Year</span>
          <input
            className="agt-number"
            disabled={disabled}
            max={2100}
            min={1900}
            onChange={(event) => {
              updateHardFilters({
                max_year: event.target.value === "" ? null : Number(event.target.value),
              });
            }}
            type="number"
            value={filterDraft.hard_filters.max_year ?? ""}
          />
        </label>
      </div>
      <div className="agt-grid">
        <label className="agt-field">
          <span>Min Citations</span>
          <input
            className="agt-number"
            disabled={disabled}
            min={0}
            onChange={(event) => {
              const value = Number(event.target.value);
              updateHardFilters({ min_citations: Number.isNaN(value) ? 0 : value });
            }}
            type="number"
            value={filterDraft.hard_filters.min_citations}
          />
        </label>
        <label className="agt-field">
          <span>Max Citations</span>
          <input
            className="agt-number"
            disabled={disabled}
            min={0}
            onChange={(event) => {
              updateHardFilters({
                max_citations: event.target.value === "" ? null : Number(event.target.value),
              });
            }}
            type="number"
            value={filterDraft.hard_filters.max_citations ?? ""}
          />
        </label>
      </div>
      <div className="agt-grid">
        <label className="agt-field">
          <span>Required terms / keywords</span>
          <textarea
            className="agt-textarea"
            disabled={disabled}
            onChange={(event) => {
              updateHardFilters({ include_keywords: parseKeywordList(event.target.value) });
            }}
            rows={3}
            value={keywordListToText(filterDraft.hard_filters.include_keywords)}
          />
        </label>
        <label className="agt-field">
          <span>Exclude Keywords</span>
          <textarea
            className="agt-textarea"
            disabled={disabled}
            onChange={(event) => {
              updateHardFilters({ exclude_keywords: parseKeywordList(event.target.value) });
            }}
            rows={3}
            value={keywordListToText(filterDraft.hard_filters.exclude_keywords)}
          />
        </label>
      </div>
      {onSuggestAuthors !== undefined ? (
        <div className="agt-field">
          <span>Author Filter</span>
          <AuthorChipInput
            authors={filterDraft.authors ?? []}
            disabled={disabled}
            onChange={(next) => update({ ...filterDraft, authors: next })}
            onSuggest={onSuggestAuthors}
          />
        </div>
      ) : null}
      {onSuggestVenues !== undefined ? (
        <div className="agt-field">
          <span>Venue / Journal Filter</span>
          <VenueChipInput
            venues={filterDraft.venues ?? []}
            disabled={disabled}
            onChange={(next) => update({ ...filterDraft, venues: next })}
            onSuggest={onSuggestVenues}
          />
        </div>
      ) : null}
      <div className="agt-field">
        <span>Seed Papers (DOI, one per line)</span>
        <textarea
          className="agt-textarea"
          disabled={disabled}
          onChange={(event) => {
            update({
              ...filterDraft,
              seed_dois: event.target.value
                .split("\n")
                .map((line) => line.trim())
                .filter((line) => line.length > 0),
            });
          }}
          placeholder={"10.1038/nature12373\n10.1126/science.1234567"}
          rows={3}
          value={(filterDraft.seed_dois ?? []).join("\n")}
        />
        <span className="agt-hint">Papers whose citation graph to include. One DOI per line.</span>
      </div>
      <div className="agt-checkbox-row">
        <label className="agt-checkbox-row">
          <input
            checked={filterDraft.hard_filters.open_access_only}
            disabled={disabled}
            onChange={(event) => updateHardFilters({ open_access_only: event.target.checked })}
            type="checkbox"
          />
          <span>Open access only</span>
        </label>
        <label className="agt-checkbox-row">
          <input
            checked={filterDraft.soft_preferences.require_positive_community_perception}
            disabled={disabled}
            onChange={(event) => {
              updateSoftPreferences({
                require_positive_community_perception: event.target.checked,
              });
            }}
            type="checkbox"
          />
          <span>Require positive community perception</span>
        </label>
      </div>
      <div className="agt-subpanel">
        <div className="agt-section-heading">
          <h3>Source Enforcement</h3>
        </div>
        {searchPlan !== null ? (
          <>
            <div className="agt-chip-list">
              {searchPlan.filters_enforced_post_merge.map((filterName) => (
                <span className="agt-chip agt-chip--warn" key={filterName}>
                  post-merge: {filterName}
                </span>
              ))}
              {searchPlan.filters_enforced_post_merge.length === 0 ? (
                <span className="agt-chip">No post-merge filters active</span>
              ) : null}
            </div>
            <div className="agt-chip-list">
              {searchPlan.source_policy.map((source) => (
                <span className="agt-chip" key={source.name}>
                  {source.name}
                  {source.supports_year_filter ? " year" : " no-year"}
                  {source.supports_open_access_filter ? " oa" : ""}
                </span>
              ))}
            </div>
          </>
        ) : (
          <p className="agt-empty-state">Source enforcement details appear after the first search.</p>
        )}
      </div>
    </section>
  );
}
