import { startTransition, useEffect, useEffectEvent, useRef, useState } from "react";

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
  type DoctorReport,
  type FilterEditContract,
  type GapFinderResponse,
  type HealthResponse,
  type KeyValidateResponse,
  type NormalizedPaper,
  type ProviderInfo,
  type SearchMetadata,
  type SearchPlan,
  type SourceCapability,
  type StatusResponse,
  type Watch,
  type WatchRerunResponse,
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
  const [providers, setProviders] = useState<Record<string, ProviderInfo>>({});
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
  const [searchDepth, setSearchDepth] = useState<"quick" | "balanced" | "deep">("balanced");
  const [correctedQuery, setCorrectedQuery] = useState<string | null>(null);
  const [extracting, setExtracting] = useState(false);
  const [extractError, setExtractError] = useState<string | null>(null);
  const [doctorReport, setDoctorReport] = useState<DoctorReport | null>(null);
  const [doctorScanning, setDoctorScanning] = useState(false);
  const [doctorError, setDoctorError] = useState<string | null>(null);
  const [gapResult, setGapResult] = useState<GapFinderResponse | null>(null);
  const [gapRunning, setGapRunning] = useState(false);
  const [gapError, setGapError] = useState<string | null>(null);
  const [watches, setWatches] = useState<Watch[]>([]);
  const [watchesLoading, setWatchesLoading] = useState(false);
  const [watchesError, setWatchesError] = useState<string | null>(null);
  const [watchName, setWatchName] = useState("");
  const [watchSaving, setWatchSaving] = useState(false);
  const [watchSaveError, setWatchSaveError] = useState<string | null>(null);
  const [rerunningWatchId, setRerunningWatchId] = useState<string | null>(null);
  const [lastWatchRerun, setLastWatchRerun] = useState<WatchRerunResponse | null>(null);

  // Tracks whether the current config state was changed by the user (vs loaded from prefs).
  const configChangedByUserRef = useRef(false);

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
          return {
            ...filterEditFromSearchPlan(
              statusSearchPlan.original_query,
              statusSearchPlan,
              resultLimit,
            ),
            authors: currentDraft?.authors ?? [],
            venues: currentDraft?.venues ?? [],
            seed_dois: currentDraft?.seed_dois ?? [],
          };
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
      try {
        const prov = await client.providers();
        setProviders(prov);
      } catch {
        // Non-fatal: providers endpoint unavailable on older backends.
        setProviders({});
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

  const saveFirstRunConfig = useEffectEvent(async (update: Partial<AddonConfig>) => {
    setSaveState("saving");
    setSaveError(null);
    try {
      const nextConfig = await services.saveConfig({ ...config, ...update });
      setConfig(nextConfig);
      setSaveState("saved");
      void refreshHealth(nextConfig);
    } catch (error) {
      setSaveError(describeError(error));
      setSaveState("error");
    }
  });

  // Silent auto-save — writes prefs without triggering a health refresh.
  const autoSaveConfig = useEffectEvent(async () => {
    try {
      const nextConfig = await services.saveConfig(config);
      setConfig(nextConfig);
    } catch {
      // Auto-save failures are silent; explicit Save button remains available.
    }
  });

  const dismissBanner = useEffectEvent(async () => {
    try {
      const next = await services.saveConfig({ ...config, bannerDismissed: true });
      setConfig(next);
    } catch {
      // non-fatal
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

    const isRerun = runView.snapshot !== null;
    setNativeWriteResult(null);
    setRunView({ error: null, phase: "submitting", snapshot: runView.snapshot });
    try {
      const response = await services.createClient(config).run({
        collection_name: collectionName.trim() || "Inbox",
        filter_edit:
          filterDraft !== null && filterDraft.original_query.trim() === trimmedQuery
            ? filterDraft
            : undefined,
        force_refresh: isRerun ? true : undefined,
        query: trimmedQuery,
        search_depth: searchDepth,
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
        enable_pdf_imports: approved && config.enablePdfImports && !useNative ? true : undefined,
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

  const runLibraryDoctor = useEffectEvent(async () => {
    const cn = collectionName.trim() || "Inbox";
    setDoctorScanning(true);
    setDoctorError(null);
    setDoctorReport(null);
    try {
      const result = await services.createClient(config).libraryDoctor(cn);
      setDoctorReport(result);
    } catch (error) {
      setDoctorError(describeError(error));
    } finally {
      setDoctorScanning(false);
    }
  });

  const runGapFinder = useEffectEvent(async () => {
    const cn = collectionName.trim() || "Inbox";
    setGapRunning(true);
    setGapError(null);
    setGapResult(null);
    try {
      const result = await services.createClient(config).gapFinder(cn);
      setGapResult(result);
    } catch (error) {
      setGapError(describeError(error));
    } finally {
      setGapRunning(false);
    }
  });

  const loadWatches = useEffectEvent(async () => {
    setWatchesLoading(true);
    setWatchesError(null);
    try {
      const loaded = await services.createClient(config).listWatches();
      setWatches(loaded);
    } catch (error) {
      setWatchesError(describeError(error));
    } finally {
      setWatchesLoading(false);
    }
  });

  const saveWatch = useEffectEvent(async () => {
    const trimmed = query.trim();
    const name = watchName.trim();
    if (trimmed.length === 0 || name.length === 0) return;
    setWatchSaving(true);
    setWatchSaveError(null);
    try {
      await services.createClient(config).createWatch(
        name,
        trimmed,
        collectionName.trim() || null,
        filterDraft,
      );
      setWatchName("");
      await loadWatches();
    } catch (error) {
      setWatchSaveError(describeError(error));
    } finally {
      setWatchSaving(false);
    }
  });

  const deleteWatchById = useEffectEvent(async (watchId: string) => {
    try {
      await services.createClient(config).deleteWatch(watchId);
      setWatches((current) => current.filter((w) => w.id !== watchId));
    } catch (error) {
      setWatchesError(describeError(error));
    }
  });

  const rerunWatchById = useEffectEvent(async (watchId: string) => {
    setRerunningWatchId(watchId);
    setLastWatchRerun(null);
    setNativeWriteResult(null);
    setRunView({ error: null, phase: "submitting", snapshot: runView.snapshot });
    try {
      const rerunResp = await services.createClient(config).rerunWatch(watchId);
      setLastWatchRerun(rerunResp);
      await fetchStatus(rerunResp.run_id);
      await loadWatches();
    } catch (error) {
      setRunView({ error: describeError(error), phase: "error", snapshot: runView.snapshot });
    } finally {
      setRerunningWatchId(null);
    }
  });

  const validateKey = useEffectEvent(
    async (provider: string, apiKey: string): Promise<KeyValidateResponse> => {
      return services.createClient(config).validateKey(provider, apiKey);
    },
  );

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

  // Auto-save whenever the user changes a preference (debounced 800 ms).
  useEffect(() => {
    if (!configChangedByUserRef.current) return;
    const timer = setTimeout(() => {
      configChangedByUserRef.current = false;
      void autoSaveConfig();
    }, 800);
    return () => clearTimeout(timer);
  }, []);

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

  useEffect(() => {
    void loadWatches();
  }, []);

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
    doctorError,
    doctorReport,
    doctorScanning,
    extractError,
    extracting,
    gapError,
    gapResult,
    gapRunning,
    onDismissBanner: () => void dismissBanner(),
    onExtractKeywords: () => void runExtractKeywords(),
    onLibraryDoctor: () => void runLibraryDoctor(),
    onGapFinder: () => void runGapFinder(),
    lastWatchRerun,
    onDeleteWatch: (watchId: string) => void deleteWatchById(watchId),
    onRerunWatch: (watchId: string) => void rerunWatchById(watchId),
    onSaveWatch: () => void saveWatch(),
    onWatchNameChange: setWatchName,
    rerunningWatchId,
    watchName,
    watchSaveError,
    watchSaving,
    watches,
    watchesError,
    watchesLoading,
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
      configChangedByUserRef.current = true;
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
    onSaveFirstRunConfig: (update: Partial<AddonConfig>) => void saveFirstRunConfig(update),
    onSuggestAuthors: (q: string) => services.createClient(config).suggestAuthors(q),
    onSuggestVenues: (q: string) => services.createClient(config).suggestVenues(q),
    onSubmitSearch: () => void submitSearch(),
    validateKey: (provider: string, apiKey: string) => validateKey(provider, apiKey),
    onDepthChange: setSearchDepth,
    searchDepth,
    onToggleSelection: (index: number) => {
      setSelectedIndices((currentSelection) => {
        if (currentSelection.includes(index)) {
          return currentSelection.filter((value) => value !== index);
        }
        return uniqueSortedIndices([...currentSelection, index]);
      });
    },
    papers,
    providers,
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
