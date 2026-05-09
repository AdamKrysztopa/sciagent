import type { FilterEditContract, SearchPlan } from "../../shared/contracts";
import { keywordListToText, parseKeywordList } from "../../shared/contracts";

interface FilterEditorProps {
  disabled: boolean;
  filterDraft: FilterEditContract | null;
  onChange(nextDraft: FilterEditContract): void;
  onReset(): void;
  searchPlan: SearchPlan | null;
}

export function FilterEditor({
  disabled,
  filterDraft,
  onChange,
  onReset,
  searchPlan,
}: FilterEditorProps) {
  if (filterDraft === null || searchPlan === null) {
    return (
      <section className="agt-card agt-card--soft">
        <div className="agt-section-heading">
          <h2>Parsed Filters</h2>
        </div>
        <p className="agt-empty-state">
          Run a search first. The add-on reads the backend search plan from <code>/status</code>, then lets you review and edit the structured filter contract before re-running.
        </p>
      </section>
    );
  }

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
        <h2>Parsed Filters</h2>
        <button className="agt-button agt-button--ghost" disabled={disabled} onClick={onReset} type="button">
          Reset To Parsed Plan
        </button>
      </div>
      <p className="agt-hint">
        These controls mirror the backend <code>FilterEditContract</code>. Re-running search sends the edited payload back through <code>/run</code>.
      </p>
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
          <span>Include Keywords</span>
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
      <div className="agt-card agt-card--soft">
        <div className="agt-section-heading">
          <h3>Source Enforcement</h3>
        </div>
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
      </div>
    </section>
  );
}
