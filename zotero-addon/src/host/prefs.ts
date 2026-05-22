import type { ZoteroGlobal } from "./zoteroTypes";

export interface AddonConfig {
  apiKey: string;
  backendUrl: string;
  clientId: string;
  enablePdfImports: boolean;
  /** When true, the addon writes to Zotero natively (ZAP-6/7/8) instead of via pyzotero. */
  nativeWriteEnabled: boolean;
  // Search Defaults (M6.1-A)
  defaultCollection: string;
  defaultMinYear: number | null;
  defaultMaxYear: number | null;
  defaultMinCitations: number;
  defaultOpenAccessOnly: boolean;
  spellCheckEnabled: boolean;
  // LLM Provider selection (SCI-0603)
  llmProvider: string;
  openaiApiKey: string;
  anthropicApiKey: string;
  xaiApiKey: string;
  groqApiKey: string;
  llmBaseUrl: string;
  llmModel: string;
  // Backend mode — "local" spawns embedded server, "remote" connects to backendUrl (SCI-0604)
  backendMode: string;
  // First-run capability banner (OPN-16)
  bannerDismissed: boolean;
  // Zotero credentials for remote backend mode (MU2)
  zoteroApiKey: string;
  zoteroLibraryId: string;
  zoteroLibraryType: "user" | "group";
  // LLM override for remote backend mode (MU2)
  useCustomLlm: boolean;
  customLlmProvider: string;
  customLlmBaseUrl: string;
  customLlmModel: string;
  customLlmApiKey: string;
}

export interface PreferenceStore {
  readConfig(): AddonConfig;
  writeConfig(update: Partial<AddonConfig>): AddonConfig;
}

export const PREF_KEYS = {
  apiKey: "extensions.agt.apiKey",
  backendUrl: "extensions.agt.backendURL",
  clientId: "extensions.agt.clientID",
  enablePdfImports: "extensions.agt.enablePDFImports",
  nativeWriteEnabled: "extensions.agt.nativeWriteEnabled",
  defaultCollection: "extensions.agt.defaultCollection",
  defaultMinYear: "extensions.agt.defaultMinYear",
  defaultMaxYear: "extensions.agt.defaultMaxYear",
  defaultMinCitations: "extensions.agt.defaultMinCitations",
  defaultOpenAccessOnly: "extensions.agt.defaultOpenAccessOnly",
  spellCheckEnabled: "extensions.agt.spellCheckEnabled",
  // LLM Provider (SCI-0603)
  llmProvider: "extensions.agt.llmProvider",
  openaiApiKey: "extensions.agt.openaiApiKey",
  anthropicApiKey: "extensions.agt.anthropicApiKey",
  xaiApiKey: "extensions.agt.xaiApiKey",
  groqApiKey: "extensions.agt.groqApiKey",
  llmBaseUrl: "extensions.agt.llmBaseUrl",
  llmModel: "extensions.agt.llmModel",
  // Backend mode (SCI-0604)
  backendMode: "extensions.agt.backendMode",
  // First-run capability banner (OPN-16)
  bannerDismissed: "extensions.agt.bannerDismissed",
  // Zotero credentials for remote backend mode (MU2)
  zoteroApiKey: "extensions.agt.zoteroApiKey",
  zoteroLibraryId: "extensions.agt.zoteroLibraryId",
  zoteroLibraryType: "extensions.agt.zoteroLibraryType",
  // LLM override for remote backend mode (MU2)
  useCustomLlm: "extensions.agt.useCustomLlm",
  customLlmProvider: "extensions.agt.customLlmProvider",
  customLlmBaseUrl: "extensions.agt.customLlmBaseUrl",
  customLlmModel: "extensions.agt.customLlmModel",
  customLlmApiKey: "extensions.agt.customLlmApiKey",
} as const;

export const DEFAULT_ADDON_CONFIG: AddonConfig = {
  apiKey: "",
  backendUrl: "http://127.0.0.1:8000",
  clientId: "zotero-local",
  enablePdfImports: false,
  nativeWriteEnabled: false,
  defaultCollection: "Inbox",
  defaultMinYear: null,
  defaultMaxYear: null,
  defaultMinCitations: 0,
  defaultOpenAccessOnly: false,
  spellCheckEnabled: true,
  // LLM Provider (SCI-0603)
  llmProvider: "openai",
  openaiApiKey: "",
  anthropicApiKey: "",
  xaiApiKey: "",
  groqApiKey: "",
  llmBaseUrl: "",
  llmModel: "",
  // Backend mode (SCI-0604 / P9.0): "local" spawns the embedded server binary;
  // "remote" connects to backendUrl set by the user in preferences.
  backendMode: "local",
  // First-run capability banner (OPN-16)
  bannerDismissed: false,
  // Zotero credentials for remote backend mode (MU2)
  zoteroApiKey: "",
  zoteroLibraryId: "",
  zoteroLibraryType: "user",
  // LLM override for remote backend mode (MU2)
  useCustomLlm: false,
  customLlmProvider: "",
  customLlmBaseUrl: "",
  customLlmModel: "",
  customLlmApiKey: "",
};

function normalizeBackendUrl(value: string): string {
  const trimmed = value.trim();
  return trimmed.replace(/\/+$/, "") || DEFAULT_ADDON_CONFIG.backendUrl;
}

function readStringPref(zotero: ZoteroGlobal, key: string, fallback: string): string {
  const rawValue = zotero.Prefs.get(key);
  return typeof rawValue === "string" && rawValue.trim().length > 0 ? rawValue.trim() : fallback;
}

function readBooleanPref(zotero: ZoteroGlobal, key: string, fallback: boolean): boolean {
  const rawValue = zotero.Prefs.get(key);
  return typeof rawValue === "boolean" ? rawValue : fallback;
}

function readNullableIntPref(zotero: ZoteroGlobal, key: string): number | null {
  const rawValue = zotero.Prefs.get(key);
  if (typeof rawValue === "number") return Math.round(rawValue);
  if (typeof rawValue === "string" && rawValue.trim().length > 0) {
    const n = parseInt(rawValue.trim(), 10);
    return Number.isNaN(n) ? null : n;
  }
  return null;
}

function readIntPref(zotero: ZoteroGlobal, key: string, fallback: number): number {
  const rawValue = zotero.Prefs.get(key);
  if (typeof rawValue === "number") return Math.round(rawValue);
  if (typeof rawValue === "string" && rawValue.trim().length > 0) {
    const n = parseInt(rawValue.trim(), 10);
    return Number.isNaN(n) ? fallback : n;
  }
  return fallback;
}

export function createZoteroPreferenceStore(zotero: ZoteroGlobal): PreferenceStore {
  return {
    readConfig(): AddonConfig {
      return {
        apiKey: readStringPref(zotero, PREF_KEYS.apiKey, DEFAULT_ADDON_CONFIG.apiKey),
        backendUrl: normalizeBackendUrl(
          readStringPref(zotero, PREF_KEYS.backendUrl, DEFAULT_ADDON_CONFIG.backendUrl),
        ),
        clientId: readStringPref(zotero, PREF_KEYS.clientId, DEFAULT_ADDON_CONFIG.clientId),
        enablePdfImports: readBooleanPref(
          zotero,
          PREF_KEYS.enablePdfImports,
          DEFAULT_ADDON_CONFIG.enablePdfImports,
        ),
        nativeWriteEnabled: readBooleanPref(
          zotero,
          PREF_KEYS.nativeWriteEnabled,
          DEFAULT_ADDON_CONFIG.nativeWriteEnabled,
        ),
        defaultCollection: readStringPref(
          zotero,
          PREF_KEYS.defaultCollection,
          DEFAULT_ADDON_CONFIG.defaultCollection,
        ),
        defaultMinYear: readNullableIntPref(zotero, PREF_KEYS.defaultMinYear),
        defaultMaxYear: readNullableIntPref(zotero, PREF_KEYS.defaultMaxYear),
        defaultMinCitations: readIntPref(
          zotero,
          PREF_KEYS.defaultMinCitations,
          DEFAULT_ADDON_CONFIG.defaultMinCitations,
        ),
        defaultOpenAccessOnly: readBooleanPref(
          zotero,
          PREF_KEYS.defaultOpenAccessOnly,
          DEFAULT_ADDON_CONFIG.defaultOpenAccessOnly,
        ),
        spellCheckEnabled: readBooleanPref(
          zotero,
          PREF_KEYS.spellCheckEnabled,
          DEFAULT_ADDON_CONFIG.spellCheckEnabled,
        ),
        llmProvider: readStringPref(
          zotero,
          PREF_KEYS.llmProvider,
          DEFAULT_ADDON_CONFIG.llmProvider,
        ),
        openaiApiKey: readStringPref(
          zotero,
          PREF_KEYS.openaiApiKey,
          DEFAULT_ADDON_CONFIG.openaiApiKey,
        ),
        anthropicApiKey: readStringPref(
          zotero,
          PREF_KEYS.anthropicApiKey,
          DEFAULT_ADDON_CONFIG.anthropicApiKey,
        ),
        xaiApiKey: readStringPref(zotero, PREF_KEYS.xaiApiKey, DEFAULT_ADDON_CONFIG.xaiApiKey),
        groqApiKey: readStringPref(zotero, PREF_KEYS.groqApiKey, DEFAULT_ADDON_CONFIG.groqApiKey),
        llmBaseUrl: readStringPref(zotero, PREF_KEYS.llmBaseUrl, DEFAULT_ADDON_CONFIG.llmBaseUrl),
        llmModel: readStringPref(zotero, PREF_KEYS.llmModel, DEFAULT_ADDON_CONFIG.llmModel),
        backendMode: readStringPref(
          zotero,
          PREF_KEYS.backendMode,
          DEFAULT_ADDON_CONFIG.backendMode,
        ),
        bannerDismissed: readBooleanPref(
          zotero,
          PREF_KEYS.bannerDismissed,
          DEFAULT_ADDON_CONFIG.bannerDismissed,
        ),
        zoteroApiKey: readStringPref(zotero, PREF_KEYS.zoteroApiKey, DEFAULT_ADDON_CONFIG.zoteroApiKey),
        zoteroLibraryId: readStringPref(zotero, PREF_KEYS.zoteroLibraryId, DEFAULT_ADDON_CONFIG.zoteroLibraryId),
        zoteroLibraryType: readStringPref(zotero, PREF_KEYS.zoteroLibraryType, DEFAULT_ADDON_CONFIG.zoteroLibraryType) as "user" | "group",
        useCustomLlm: readBooleanPref(zotero, PREF_KEYS.useCustomLlm, DEFAULT_ADDON_CONFIG.useCustomLlm),
        customLlmProvider: readStringPref(zotero, PREF_KEYS.customLlmProvider, DEFAULT_ADDON_CONFIG.customLlmProvider),
        customLlmBaseUrl: readStringPref(zotero, PREF_KEYS.customLlmBaseUrl, DEFAULT_ADDON_CONFIG.customLlmBaseUrl),
        customLlmModel: readStringPref(zotero, PREF_KEYS.customLlmModel, DEFAULT_ADDON_CONFIG.customLlmModel),
        customLlmApiKey: readStringPref(zotero, PREF_KEYS.customLlmApiKey, DEFAULT_ADDON_CONFIG.customLlmApiKey),
      };
    },

    writeConfig(update: Partial<AddonConfig>): AddonConfig {
      const nextConfig = {
        ...this.readConfig(),
        ...update,
      };

      nextConfig.backendUrl = normalizeBackendUrl(nextConfig.backendUrl);
      nextConfig.clientId = nextConfig.clientId.trim() || DEFAULT_ADDON_CONFIG.clientId;
      nextConfig.apiKey = nextConfig.apiKey.trim();
      nextConfig.defaultCollection = nextConfig.defaultCollection.trim() || DEFAULT_ADDON_CONFIG.defaultCollection;
      nextConfig.defaultMinCitations = Math.max(0, nextConfig.defaultMinCitations);

      zotero.Prefs.set(PREF_KEYS.backendUrl, nextConfig.backendUrl);
      zotero.Prefs.set(PREF_KEYS.apiKey, nextConfig.apiKey);
      zotero.Prefs.set(PREF_KEYS.clientId, nextConfig.clientId);
      zotero.Prefs.set(PREF_KEYS.enablePdfImports, nextConfig.enablePdfImports);
      zotero.Prefs.set(PREF_KEYS.nativeWriteEnabled, nextConfig.nativeWriteEnabled);
      zotero.Prefs.set(PREF_KEYS.defaultCollection, nextConfig.defaultCollection);
      zotero.Prefs.set(
        PREF_KEYS.defaultMinYear,
        nextConfig.defaultMinYear !== null ? nextConfig.defaultMinYear : "",
      );
      zotero.Prefs.set(
        PREF_KEYS.defaultMaxYear,
        nextConfig.defaultMaxYear !== null ? nextConfig.defaultMaxYear : "",
      );
      zotero.Prefs.set(PREF_KEYS.defaultMinCitations, nextConfig.defaultMinCitations);
      zotero.Prefs.set(PREF_KEYS.defaultOpenAccessOnly, nextConfig.defaultOpenAccessOnly);
      zotero.Prefs.set(PREF_KEYS.spellCheckEnabled, nextConfig.spellCheckEnabled);
      zotero.Prefs.set(PREF_KEYS.llmProvider, nextConfig.llmProvider);
      zotero.Prefs.set(PREF_KEYS.openaiApiKey, nextConfig.openaiApiKey);
      zotero.Prefs.set(PREF_KEYS.anthropicApiKey, nextConfig.anthropicApiKey);
      zotero.Prefs.set(PREF_KEYS.xaiApiKey, nextConfig.xaiApiKey);
      zotero.Prefs.set(PREF_KEYS.groqApiKey, nextConfig.groqApiKey);
      zotero.Prefs.set(PREF_KEYS.llmBaseUrl, nextConfig.llmBaseUrl);
      zotero.Prefs.set(PREF_KEYS.llmModel, nextConfig.llmModel);
      zotero.Prefs.set(PREF_KEYS.backendMode, nextConfig.backendMode);
      zotero.Prefs.set(PREF_KEYS.bannerDismissed, nextConfig.bannerDismissed);
      zotero.Prefs.set(PREF_KEYS.zoteroApiKey, nextConfig.zoteroApiKey.trim());
      zotero.Prefs.set(PREF_KEYS.zoteroLibraryId, nextConfig.zoteroLibraryId.trim());
      zotero.Prefs.set(PREF_KEYS.zoteroLibraryType, nextConfig.zoteroLibraryType);
      zotero.Prefs.set(PREF_KEYS.useCustomLlm, nextConfig.useCustomLlm);
      zotero.Prefs.set(PREF_KEYS.customLlmProvider, nextConfig.customLlmProvider.trim());
      zotero.Prefs.set(PREF_KEYS.customLlmBaseUrl, nextConfig.customLlmBaseUrl.trim());
      zotero.Prefs.set(PREF_KEYS.customLlmModel, nextConfig.customLlmModel.trim());
      zotero.Prefs.set(PREF_KEYS.customLlmApiKey, nextConfig.customLlmApiKey.trim());

      return nextConfig;
    },
  };
}

/**
 * Returns true when the given URL uses the insecure `http://` scheme.
 * Used by the UI to block remote-backend connections that are not HTTPS.
 */
export function isInsecureUrl(url: string): boolean {
  return url.startsWith("http://");
}

/**
 * Collect LLM provider env vars from the add-on config for passing to the
 * embedded server process (SCI-0603/0604).
 */
export function collectProviderEnv(config: AddonConfig): Record<string, string> {
  const env: Record<string, string> = {};
  const provider = config.llmProvider;

  if (provider) {
    env.AGT_LLM_PROVIDER = provider === "custom" ? "openai-compatible" : provider;
  }

  if (provider === "openai" && config.openaiApiKey) {
    env.OPENAI_API_KEY = config.openaiApiKey;
  } else if (provider === "anthropic" && config.anthropicApiKey) {
    env.ANTHROPIC_API_KEY = config.anthropicApiKey;
  } else if (provider === "xai" && config.xaiApiKey) {
    env.XAI_API_KEY = config.xaiApiKey;
  } else if (provider === "groq" && config.groqApiKey) {
    env.AGT_GROQ_API_KEY = config.groqApiKey;
  }

  if (config.llmBaseUrl) env.AGT_LLM_BASE_URL = config.llmBaseUrl;
  if (config.llmModel) env.AGT_LLM_MODEL = config.llmModel;

  return env;
}
