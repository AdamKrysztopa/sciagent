import type { ZoteroGlobal } from "./zoteroTypes";

export interface AddonConfig {
  apiKey: string;
  backendUrl: string;
  clientId: string;
  enablePdfImports: boolean;
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
} as const;

export const DEFAULT_ADDON_CONFIG: AddonConfig = {
  apiKey: "",
  backendUrl: "http://127.0.0.1:8000",
  clientId: "zotero-local",
  enablePdfImports: false,
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

      zotero.Prefs.set(PREF_KEYS.backendUrl, nextConfig.backendUrl);
      zotero.Prefs.set(PREF_KEYS.apiKey, nextConfig.apiKey);
      zotero.Prefs.set(PREF_KEYS.clientId, nextConfig.clientId);
      zotero.Prefs.set(PREF_KEYS.enablePdfImports, nextConfig.enablePdfImports);

      return nextConfig;
    },
  };
}
