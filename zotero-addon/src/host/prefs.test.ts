import { describe, expect, it } from "vitest";

import {
  DEFAULT_ADDON_CONFIG,
  PREF_KEYS,
  collectProviderEnv,
  createZoteroPreferenceStore,
} from "./prefs";
import type { ZoteroGlobal } from "./zoteroTypes";

class MockPrefs {
  readonly store = new Map<string, boolean | number | string>();

  get(key: string): boolean | number | string | undefined {
    return this.store.get(key);
  }

  set(key: string, value: boolean | number | string): void {
    this.store.set(key, value);
  }
}

function createMockZotero(): ZoteroGlobal {
  const prefs = new MockPrefs();
  return {
    ItemPaneManager: {
      registerSection: () => "section-id",
      unregisterSection: () => undefined,
    },
    PreferencePanes: {
      register: () => undefined,
    },
    Prefs: prefs,
    Collections: {
      getByLibrary: () => [],
      getByParent: () => [],
      add: () => Promise.resolve({ id: 1, key: "col1", name: "Test", parentKey: false, libraryID: 1 }),
      get: () => false,
      getAsync: () => Promise.resolve(false),
    },
    Items: {
      getAll: () => [],
      getAsync: () => Promise.resolve(false),
      get: () => false,
      add: () =>
        Promise.resolve({
          id: 1,
          key: "item1",
          libraryID: 1,
          getField: () => "",
          setField: () => undefined,
          addToCollection: () => undefined,
          save: () => Promise.resolve(),
        }),
    },
    Attachments: {
      importFromURL: () => Promise.resolve(false),
    },
    Libraries: {
      getUserLibrary: () => ({ libraryID: 1, name: "My Library", editable: true }),
    },
    debug: () => undefined,
    getMainWindows: () => [],
    logError: () => undefined,
  };
}

describe("createZoteroPreferenceStore", () => {
  it("returns defaults when prefs are unset", () => {
    const store = createZoteroPreferenceStore(createMockZotero());
    expect(store.readConfig()).toEqual(DEFAULT_ADDON_CONFIG);
  });

  it("normalizes and persists updated connection values", () => {
    const zotero = createMockZotero();
    const store = createZoteroPreferenceStore(zotero);
    const next = store.writeConfig({
      apiKey: "  secret  ",
      backendUrl: "http://localhost:8000/",
      clientId: "sidebar-user",
      enablePdfImports: true,
    });

    expect(next.apiKey).toBe("secret");
    expect(next.backendUrl).toBe("http://localhost:8000");
    expect(next.clientId).toBe("sidebar-user");
    expect(next.enablePdfImports).toBe(true);

    expect(zotero.Prefs.get(PREF_KEYS.backendUrl)).toBe("http://localhost:8000");
    expect(zotero.Prefs.get(PREF_KEYS.apiKey)).toBe("secret");
    expect(zotero.Prefs.get(PREF_KEYS.clientId)).toBe("sidebar-user");
    expect(zotero.Prefs.get(PREF_KEYS.enablePdfImports)).toBe(true);
  });

  it("persists and reads back search default fields", () => {
    const zotero = createMockZotero();
    const store = createZoteroPreferenceStore(zotero);
    const next = store.writeConfig({
      defaultCollection: "My Papers",
      defaultMinYear: 2020,
      defaultMaxYear: 2026,
      defaultMinCitations: 5,
      defaultOpenAccessOnly: true,
    });

    expect(next.defaultCollection).toBe("My Papers");
    expect(next.defaultMinYear).toBe(2020);
    expect(next.defaultMaxYear).toBe(2026);
    expect(next.defaultMinCitations).toBe(5);
    expect(next.defaultOpenAccessOnly).toBe(true);

    // Values persisted to prefs
    expect(zotero.Prefs.get(PREF_KEYS.defaultCollection)).toBe("My Papers");
    expect(zotero.Prefs.get(PREF_KEYS.defaultMinYear)).toBe(2020);
    expect(zotero.Prefs.get(PREF_KEYS.defaultMaxYear)).toBe(2026);
    expect(zotero.Prefs.get(PREF_KEYS.defaultMinCitations)).toBe(5);
    expect(zotero.Prefs.get(PREF_KEYS.defaultOpenAccessOnly)).toBe(true);

    // Read back
    const read = store.readConfig();
    expect(read.defaultCollection).toBe("My Papers");
    expect(read.defaultMinYear).toBe(2020);
    expect(read.defaultMaxYear).toBe(2026);
    expect(read.defaultMinCitations).toBe(5);
    expect(read.defaultOpenAccessOnly).toBe(true);
  });

  it("stores null year defaults as empty string and reads them back as null", () => {
    const zotero = createMockZotero();
    const store = createZoteroPreferenceStore(zotero);
    store.writeConfig({ defaultMinYear: null, defaultMaxYear: null });

    expect(zotero.Prefs.get(PREF_KEYS.defaultMinYear)).toBe("");
    expect(zotero.Prefs.get(PREF_KEYS.defaultMaxYear)).toBe("");
    expect(store.readConfig().defaultMinYear).toBeNull();
    expect(store.readConfig().defaultMaxYear).toBeNull();
  });
});

describe("collectProviderEnv", () => {
  it("sets OPENAI_API_KEY when provider is openai", () => {
    const env = collectProviderEnv({ ...DEFAULT_ADDON_CONFIG, llmProvider: "openai", openaiApiKey: "sk-test" });
    expect(env["OPENAI_API_KEY"]).toBe("sk-test");
    expect(env["AGT_LLM_PROVIDER"]).toBe("openai");
  });

  it("sets no API key for ollama and uses ollama provider name", () => {
    const env = collectProviderEnv({ ...DEFAULT_ADDON_CONFIG, llmProvider: "ollama" });
    expect(env["AGT_LLM_PROVIDER"]).toBe("ollama");
    expect(env["OPENAI_API_KEY"]).toBeUndefined();
  });

  it("maps custom provider to openai-compatible and sets base url", () => {
    const env = collectProviderEnv({
      ...DEFAULT_ADDON_CONFIG,
      llmProvider: "custom",
      llmBaseUrl: "https://api.deepseek.com/v1",
    });
    expect(env["AGT_LLM_PROVIDER"]).toBe("openai-compatible");
    expect(env["AGT_LLM_BASE_URL"]).toBe("https://api.deepseek.com/v1");
  });

  it("sets AGT_LLM_MODEL when model is provided", () => {
    const env = collectProviderEnv({ ...DEFAULT_ADDON_CONFIG, llmProvider: "ollama", llmModel: "llama3.2" });
    expect(env["AGT_LLM_MODEL"]).toBe("llama3.2");
  });
});
