import type { ZoteroGlobal } from "./zoteroTypes";

export interface AddonConfig {
  apiKey: string;
  backendUrl: string;
  clientId: string;
  enablePdfImports: boolean;
  // Search Defaults (M6.1-A)
  defaultCollection: string;
  defaultMinYear: number | null;
  defaultMaxYear: number | null;
  defaultMinCitations: number;
  defaultOpenAccessOnly: boolean;
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
  defaultCollection: "extensions.agt.defaultCollection",
  defaultMinYear: "extensions.agt.defaultMinYear",
  defaultMaxYear: "extensions.agt.defaultMaxYear",
  defaultMinCitations: "extensions.agt.defaultMinCitations",
  defaultOpenAccessOnly: "extensions.agt.defaultOpenAccessOnly",
} as const;

export const DEFAULT_ADDON_CONFIG: AddonConfig = {
  apiKey: "",
  backendUrl: "http://127.0.0.1:8000",
  clientId: "zotero-local",
  enablePdfImports: false,
  defaultCollection: "Inbox",
  defaultMinYear: null,
  defaultMaxYear: null,
  defaultMinCitations: 0,
  defaultOpenAccessOnly: false,
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

      return nextConfig;
    },
  };
}
