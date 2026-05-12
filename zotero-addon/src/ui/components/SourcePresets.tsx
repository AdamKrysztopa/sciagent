import type { FilterEditContract } from "../../shared/contracts";

interface Preset {
  label: string;
  description: string;
  apply(draft: FilterEditContract): FilterEditContract;
}

const CURRENT_YEAR = new Date().getFullYear();

const PRESETS: Preset[] = [
  {
    label: "Balanced",
    description: "Default settings — no extra filters.",
    apply: (draft) => ({
      ...draft,
      result_limit: 10,
      hard_filters: {
        ...draft.hard_filters,
        min_year: null,
        min_citations: 0,
        open_access_only: false,
        exclude_keywords: [],
      },
      soft_preferences: { ...draft.soft_preferences, min_semantic_score: 0 },
    }),
  },
  {
    label: "Open Access",
    description: "Only open-access papers.",
    apply: (draft) => ({
      ...draft,
      hard_filters: { ...draft.hard_filters, open_access_only: true },
    }),
  },
  {
    label: "Recent (5yr)",
    description: `Published ${CURRENT_YEAR - 5}–${CURRENT_YEAR} only.`,
    apply: (draft) => ({
      ...draft,
      hard_filters: { ...draft.hard_filters, min_year: CURRENT_YEAR - 5 },
    }),
  },
  {
    label: "Highly Cited",
    description: "50+ citations — established literature.",
    apply: (draft) => ({
      ...draft,
      hard_filters: { ...draft.hard_filters, min_citations: 50 },
    }),
  },
  {
    label: "Quick (5)",
    description: "Top 5 results only — fast exploration.",
    apply: (draft) => ({ ...draft, result_limit: 5 }),
  },
  {
    label: "Deep (20)",
    description: "Up to 20 results — thorough coverage.",
    apply: (draft) => ({ ...draft, result_limit: 20 }),
  },
];

const DEPTH_OPTIONS: Array<{ value: "quick" | "balanced" | "deep"; label: string; description: string }> = [
  { value: "quick", label: "Quick", description: "Fetches 1 page per source — fastest results." },
  { value: "balanced", label: "Balanced", description: "Default page budget — good coverage." },
  { value: "deep", label: "Deep", description: "Up to 3× more pages per source — thorough coverage." },
];

interface SourcePresetsProps {
  disabled: boolean;
  filterDraft: FilterEditContract | null;
  onChange(nextDraft: FilterEditContract): void;
  searchDepth: "quick" | "balanced" | "deep";
  onDepthChange(depth: "quick" | "balanced" | "deep"): void;
}

export function SourcePresets({ disabled, filterDraft, onChange, searchDepth, onDepthChange }: SourcePresetsProps) {
  if (filterDraft === null) {
    return null;
  }

  return (
    <div className="agt-presets">
      <span className="agt-presets-label">Presets:</span>
      {PRESETS.map((preset) => (
        <button
          className="agt-preset-chip"
          disabled={disabled}
          key={preset.label}
          onClick={() => onChange(preset.apply(filterDraft))}
          title={preset.description}
          type="button"
        >
          {preset.label}
        </button>
      ))}
      <span className="agt-presets-label">Depth:</span>
      {DEPTH_OPTIONS.map((opt) => (
        <button
          className={`agt-preset-chip${searchDepth === opt.value ? " agt-preset-chip--active" : ""}`}
          disabled={disabled}
          key={opt.value}
          onClick={() => onDepthChange(opt.value)}
          title={opt.description}
          type="button"
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}
