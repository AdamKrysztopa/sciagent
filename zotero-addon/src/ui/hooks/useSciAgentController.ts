import { startTransition, useEffect, useEffectEvent, useState } from "react";

import { BackendClientError } from "../../client/backendClient";
import {
  DEFAULT_ADDON_CONFIG,
  type AddonConfig,
} from "../../host/prefs";
import type { NativeWriteResult } from "../../host/zoteroWriter";
import {
  buildDefaultFilterEdit,
  buildSourceBuckets,
  filterEditFromSearchPlan,
  getPaperIndex,
  type CapabilitiesResponse,
  type FilterEditContract,
  type HealthResponse,
  type NormalizedPaper,
  type SearchMetadata,
  type SearchPlan,
  type SourceCapability,
  type StatusResponse,
  uniqueSortedIndices,
} from "../../shared/contracts";
import type { AddonUiServices } from "../serviceTypes";

type SaveState = "idle" | "saving" | "saved" | "error";
export type RunPhase =
  | "idle"
  | "submitting"
  | "awaiting_approval"
  | "resuming"
  | "completed"
  | "rejected"
  | "failed"
  | "error";

interface RunViewState {
  error: string | null;
  phase: RunPhase;
  snapshot: StatusResponse | null;
}

function describeError(error: unknown): string {
  if (error instanceof BackendClientError) {
    if (
      typeof error.detail === "object" &&
      error.detail !== null &&
      "detail" in error.detail &&
      typeof (error.detail as { detail: unknown }).detail === "string"
    ) {
      return `${(error.detail as { detail: string }).detail} (${error.status})`;
    }
    return `${error.message} (${error.status})`;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Unexpected add-on error";
}

export function useSciAgentController(services: AddonUiServices) {
  const [config, setConfig] = useState<AddonConfig>(DEFAULT_ADDON_CONFIG);
  const [collectionName, setCollectionName] = useState("Inbox");
  const [filterDraft, setFilterDraft] = useState<FilterEditContract | null>(null);
  const [healthBusy, setHealthBusy] = useState(false);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [healthResponse, setHealthResponse] = useState<HealthResponse | null>(null);
  const [capabilities, setCapabilities] = useState<CapabilitiesResponse | null>(null);
  const [query, setQuery] = useState("");
  const [runView, setRunView] = useState<RunViewState>({
    error: null,
    phase: "idle",
    snapshot: null,
  });
  const [nativeWriteResult, setNativeWriteResult] = useState<NativeWriteResult | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [selectedIndices, setSelectedIndices] = useState<number[]>([]);
  const [correctedQuery, setCorrectedQuery] = useState<string | null>(null);
  const [extracting, setExtracting] = useState(false);
  const [extractError, setExtractError] = useState<string | null>(null);

  const currentState = runView.snapshot?.state ?? null;
  const papers: NormalizedPaper[] = currentState?.papers ?? [];
  const searchMetadata: SearchMetadata | null = currentState?.search_metadata ?? null;
  const searchPlan: SearchPlan | null = searchMetadata?.search_plan ?? null;
  const sourceBuckets = buildSourceBuckets(searchMetadata);

  const applySnapshot = useEffectEvent((snapshot: StatusResponse) => {
    const nextState = snapshot.state;

    startTransition(() => {
      setRunView({
        error: snapshot.error,
        phase: snapshot.status,
        snapshot,
      });

      if (nextState === null) {
        return;
      }

      if (nextState.collection_name !== null) {
        setCollectionName(nextState.collection_name);
      }

      const nextPapers = nextState.papers;
      const defaultSelection = nextState.selected_indices.length > 0
        ? uniqueSortedIndices(nextState.selected_indices)
        : uniqueSortedIndices(nextPapers.map((paper, index) => getPaperIndex(paper, index)));
      setSelectedIndices(defaultSelection);

      const statusSearchPlan = nextState.search_metadata?.search_plan;
      if (statusSearchPlan !== null && statusSearchPlan !== undefined) {
        setFilterDraft((currentDraft) => {
          const resultLimit =
            currentDraft !== null && currentDraft.original_query === statusSearchPlan.original_query
              ? currentDraft.result_limit
              : Math.max(nextPapers.length, 10);
          return filterEditFromSearchPlan(
            statusSearchPlan.original_query,
            statusSearchPlan,
            resultLimit,
          );
        });
      } else {
        setFilterDraft(null);
      }
    });
  });

  const refreshHealth = useEffectEvent(async (nextConfig: AddonConfig = config) => {
    setHealthBusy(true);
    setHealthError(null);
    try {
      const client = services.createClient(nextConfig);
      const response = await client.health();
      setHealthResponse(response);
      // Fetch capabilities after a successful health check.
      try {
        const caps = await client.capabilities();
        setCapabilities(caps);
      } catch {
        // Non-fatal: capabilities unavailable on older backends.
        setCapabilities(null);
      }
    } catch (error) {
      setHealthError(describeError(error));
      setHealthResponse(null);
      setCapabilities(null);
    } finally {
      setHealthBusy(false);
    }
  });

  const saveConfig = useEffectEvent(async () => {
    setSaveState("saving");
    setSaveError(null);
    try {
      const nextConfig = await services.saveConfig(config);
      setConfig(nextConfig);
      setSaveState("saved");
      void refreshHealth(nextConfig);
    } catch (error) {
      setSaveError(describeError(error));
      setSaveState("error");
    }
  });

  const fetchStatus = useEffectEvent(async (runId: string) => {
    const snapshot = await services.createClient(config).status(runId);
    applySnapshot(snapshot);
  });

  const submitSearch = useEffectEvent(async () => {
    const trimmedQuery = query.trim();
    if (trimmedQuery.length === 0) {
      setRunView({ error: "Enter a search query first.", phase: "error", snapshot: runView.snapshot });
      return;
    }

    setNativeWriteResult(null);
    setRunView({ error: null, phase: "submitting", snapshot: runView.snapshot });
    try {
      const response = await services.createClient(config).run({
        collection_name: collectionName.trim() || "Inbox",
        filter_edit:
          filterDraft !== null && filterDraft.original_query.trim() === trimmedQuery
            ? filterDraft
            : undefined,
        query: trimmedQuery,
      });
      await fetchStatus(response.run_id);
    } catch (error) {
      setRunView({ error: describeError(error), phase: "error", snapshot: runView.snapshot });
    }
  });

  const resetRun = useEffectEvent(() => {
    setRunView({ error: null, phase: "idle", snapshot: null });
    setNativeWriteResult(null);
    setSelectedIndices([]);
  });

  const resumeRun = useEffectEvent(async (approved: boolean) => {
    const runId = runView.snapshot?.run_id;
    if (runId === undefined) {
      setRunView({ error: "No pending run to resume.", phase: "error", snapshot: runView.snapshot });
      return;
    }

    setRunView({ error: null, phase: "resuming", snapshot: runView.snapshot });
    try {
      const useNative = approved && config.nativeWriteEnabled && services.nativeWrite !== undefined;
      const response = await services.createClient(config).resume({
        approved,
        collection_name: approved ? collectionName.trim() || "Inbox" : collectionName.trim() || undefined,
        run_id: runId,
        selected_indices: approved ? selectedIndices : undefined,
        native_write: useNative ? true : undefined,
      });

      if (useNative && approved && response.approved_papers !== undefined && response.approved_papers.length > 0) {
        // ZAP-6/7/8: write to Zotero natively.
        const nativeWrite = services.nativeWrite;
        try {
          if (nativeWrite === undefined) {
            throw new Error("Native write service unavailable.");
          }

          const nativeResult = await nativeWrite(
            response.approved_papers,
            collectionName.trim() || "Inbox",
            config.enablePdfImports,
          );
          setNativeWriteResult(nativeResult);
        } catch (nativeError: unknown) {
          setRunView({
            error: `Native write failed: ${describeError(nativeError)}`,
            phase: "failed",
            snapshot: runView.snapshot,
          });
          return;
        }
      }

      await fetchStatus(response.run_id);
    } catch (error) {
      setRunView({ error: describeError(error), phase: "error", snapshot: runView.snapshot });
    }
  });

  const runExtractKeywords = useEffectEvent(async () => {
    const trimmed = query.trim();
    if (trimmed.length === 0) return;
    setExtracting(true);
    setExtractError(null);
    try {
      const result = await services.createClient(config).extractKeywords(trimmed);
      setFilterDraft((currentDraft) => {
        const base = currentDraft ?? buildDefaultFilterEdit(
          config.defaultMinYear,
          config.defaultMaxYear,
          config.defaultMinCitations,
          config.defaultOpenAccessOnly,
        );
        return {
          ...base,
          hard_filters: {
            ...base.hard_filters,
            include_keywords: result.include_keywords,
            exclude_keywords: result.exclude_keywords,
            ...(result.min_year !== null ? { min_year: result.min_year } : {}),
            ...(result.max_year !== null ? { max_year: result.max_year } : {}),
            ...(result.min_citations !== null ? { min_citations: result.min_citations } : {}),
            ...(result.max_citations !== null ? { max_citations: result.max_citations } : {}),
            open_access_only: result.open_access_only || base.hard_filters.open_access_only,
          },
        };
      });
      if (result.collection_name !== null) {
        setCollectionName(result.collection_name);
      }
    } catch (error) {
      setExtractError(describeError(error));
    } finally {
      setExtracting(false);
    }
  });

  const checkSpelling = useEffectEvent(async (trimmedQuery: string) => {
    if (healthResponse === null) {
      setCorrectedQuery(null);
      return;
    }
    try {
      const result = await services.createClient(config).correctQuery(trimmedQuery);
      setCorrectedQuery(result.changed ? result.corrected : null);
    } catch {
      setCorrectedQuery(null);
    }
  });

  useEffect(() => {
    const trimmed = query.trim();
    if (trimmed.length === 0 || !config.spellCheckEnabled) {
      setCorrectedQuery(null);
      return;
    }
    const timer = setTimeout(() => {
      void checkSpelling(trimmed);
    }, 500);
    return () => clearTimeout(timer);
  }, [query, config.spellCheckEnabled]);

  useEffect(() => {
    let cancelled = false;

    void services.loadConfig().then((loadedConfig) => {
      if (cancelled) {
        return;
      }
      setConfig(loadedConfig);
      // Seed collection name and filter draft from saved defaults (M6.1-A/B)
      setCollectionName(loadedConfig.defaultCollection || "Inbox");
      setFilterDraft((currentDraft) => {
        if (currentDraft !== null) {
          return currentDraft;
        }
        return buildDefaultFilterEdit(
          loadedConfig.defaultMinYear,
          loadedConfig.defaultMaxYear,
          loadedConfig.defaultMinCitations,
          loadedConfig.defaultOpenAccessOnly,
        );
      });
      void refreshHealth(loadedConfig);
    }).catch((error: unknown) => {
      if (cancelled) {
        return;
      }
      setSaveError(describeError(error));
      setSaveState("error");
    });

    return () => {
      cancelled = true;
    };
  }, [services]);

  return {
    canApprove: selectedIndices.length > 0 && runView.phase === "awaiting_approval",
    capabilities,
    collectionName,
    config,
    correctedQuery,
    nativeWriteResult,
    filterDraft,
    healthBusy,
    healthError,
    healthResponse,
    canSubmitSearch: query.trim().length > 0 && healthResponse !== null && !healthBusy,
    extractError,
    extracting,
    onExtractKeywords: () => void runExtractKeywords(),
    onAcceptCorrection: () => {
      if (correctedQuery !== null) {
        const accepted = correctedQuery;
        setQuery(accepted);
        setCorrectedQuery(null);
        setFilterDraft((currentDraft) => {
          if (currentDraft !== null) {
            return { ...currentDraft, original_query: accepted };
          }
          return buildDefaultFilterEdit(
            config.defaultMinYear,
            config.defaultMaxYear,
            config.defaultMinCitations,
            config.defaultOpenAccessOnly,
          );
        });
      }
    },
    onApprove: () => void resumeRun(true),
    onCollectionChange: setCollectionName,
    onConfigChange: (field: keyof AddonConfig, value: boolean | number | null | string) => {
      setConfig((currentConfig) => ({
        ...currentConfig,
        [field]: value,
      }));
      setSaveState("idle");
    },
    onFilterDraftChange: setFilterDraft,
    onQueryChange: (nextQuery: string) => {
      setQuery(nextQuery);
      const trimmedQuery = nextQuery.trim();
      setFilterDraft((currentDraft) => {
        if (currentDraft !== null) {
          return {
            ...currentDraft,
            original_query: trimmedQuery,
          };
        }
        return buildDefaultFilterEdit(
          config.defaultMinYear,
          config.defaultMaxYear,
          config.defaultMinCitations,
          config.defaultOpenAccessOnly,
        );
      });
    },
    onRefreshHealth: () => void refreshHealth(),
    onReject: () => void resumeRun(false),
    onReset: () => void resetRun(),
    onResetFilters: () => {
      if (searchPlan === null) {
        return;
      }
      setFilterDraft(
        filterEditFromSearchPlan(
          searchPlan.original_query,
          searchPlan,
          filterDraft?.result_limit ?? Math.max(papers.length, 10),
        ),
      );
    },
    onSaveConfig: () => void saveConfig(),
    onSubmitSearch: () => void submitSearch(),
    onToggleSelection: (index: number) => {
      setSelectedIndices((currentSelection) => {
        if (currentSelection.includes(index)) {
          return currentSelection.filter((value) => value !== index);
        }
        return uniqueSortedIndices([...currentSelection, index]);
      });
    },
    papers,
    query,
    runView,
    saveError,
    saveState,
    searchMetadata,
    searchPlan,
    selectedIndices,
    sourceBuckets,
    sourcePolicy: (capabilities?.source_policy ?? []) as SourceCapability[],
  };
}
