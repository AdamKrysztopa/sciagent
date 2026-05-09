import { describe, expect, it } from "vitest";

import {
  DEFAULT_ADDON_CONFIG,
  PREF_KEYS,
  createZoteroPreferenceStore,
} from "./prefs";
import type { ZoteroGlobal } from "./zoteroTypes";

class MockPrefs {
  readonly store = new Map<string, boolean | string>();

  get(key: string): boolean | string | undefined {
    return this.store.get(key);
  }

  set(key: string, value: boolean | string): void {
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

  it("normalizes and persists updated values", () => {
    const zotero = createMockZotero();
    const store = createZoteroPreferenceStore(zotero);
    const next = store.writeConfig({
      apiKey: "  secret  ",
      backendUrl: "http://localhost:8000/",
      clientId: "sidebar-user",
      enablePdfImports: true,
    });

    expect(next).toEqual({
      apiKey: "secret",
      backendUrl: "http://localhost:8000",
      clientId: "sidebar-user",
      enablePdfImports: true,
    });

    expect(zotero.Prefs.get(PREF_KEYS.backendUrl)).toBe("http://localhost:8000");
    expect(zotero.Prefs.get(PREF_KEYS.apiKey)).toBe("secret");
    expect(zotero.Prefs.get(PREF_KEYS.clientId)).toBe("sidebar-user");
    expect(zotero.Prefs.get(PREF_KEYS.enablePdfImports)).toBe(true);
  });
});
