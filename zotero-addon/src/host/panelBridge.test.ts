import { describe, expect, it } from "vitest";

import {
  PANEL_BRIDGE_PROPERTY,
  createPanelBridge,
  installPanelBridge,
  resolvePanelZotero,
} from "./panelBridge";
import type { ZoteroGlobal } from "./zoteroTypes";

function createMockZotero(): ZoteroGlobal {
  return {
    debug: () => undefined,
    logError: () => undefined,
    Prefs: {
      get: () => undefined,
      set: () => undefined,
    },
  } as unknown as ZoteroGlobal;
}

describe("panel host bridge", () => {
  it("creates a Zotero dialog payload that can be unwrapped by chrome windows", () => {
    const zotero = createMockZotero();
    const bridge = createPanelBridge(zotero);

    expect(bridge.Zotero).toBe(zotero);
    expect(bridge.wrappedJSObject).toBe(bridge);
  });

  it("resolves Zotero from a wrapped openDialog argument", () => {
    const zotero = createMockZotero();
    const bridge = createPanelBridge(zotero);
    const panelWindow = {
      arguments: [{ wrappedJSObject: bridge }],
    };

    expect(resolvePanelZotero(panelWindow)).toBe(zotero);
    expect((panelWindow as { Zotero?: ZoteroGlobal }).Zotero).toBe(zotero);
  });

  it("does not require window.arguments to be a real Array", () => {
    const zotero = createMockZotero();
    const bridge = createPanelBridge(zotero);
    const panelWindow = {
      arguments: {
        0: { wrappedJSObject: bridge },
        length: 1,
      },
    };

    expect(resolvePanelZotero(panelWindow)).toBe(zotero);
  });

  it("resolves Zotero from raw panel window arguments", () => {
    const zotero = createMockZotero();
    const bridge = createPanelBridge(zotero);
    const panelWindow = {
      wrappedJSObject: {
        arguments: [{ wrappedJSObject: bridge }],
      },
    };

    expect(resolvePanelZotero(panelWindow)).toBe(zotero);
  });

  it("resolves Zotero from a registered opener bridge", () => {
    const zotero = createMockZotero();
    const bridge = createPanelBridge(zotero);
    const opener = {};
    installPanelBridge(opener, bridge);

    expect(resolvePanelZotero({ opener })).toBe(zotero);
    expect((opener as Record<typeof PANEL_BRIDGE_PROPERTY, unknown>)[PANEL_BRIDGE_PROPERTY]).toBe(bridge);
  });

  it("resolves Zotero from a raw opener wrappedJSObject", () => {
    const zotero = createMockZotero();
    const bridge = createPanelBridge(zotero);
    const rawOpener = {};
    installPanelBridge(rawOpener, bridge);

    expect(resolvePanelZotero({ opener: { wrappedJSObject: rawOpener } })).toBe(zotero);
  });

  it("keeps searching when a cross-compartment wrapper rejects property access", () => {
    const zotero = createMockZotero();
    const bridge = createPanelBridge(zotero);
    const opener = {};
    installPanelBridge(opener, bridge);
    const inaccessibleArgument = {};
    Object.defineProperty(inaccessibleArgument, "wrappedJSObject", {
      get() {
        throw new Error("denied");
      },
    });

    expect(resolvePanelZotero({ arguments: [inaccessibleArgument], opener })).toBe(zotero);
  });

  it("returns null when no candidate exposes a Zotero host API", () => {
    expect(resolvePanelZotero({ arguments: [{ wrappedJSObject: { Zotero: { debug: () => undefined } } }] })).toBeNull();
  });

  it("rejects Zotero-shaped candidates without the preference API used by the panel", () => {
    expect(
      resolvePanelZotero({
        arguments: [
          {
            wrappedJSObject: {
              Zotero: {
                debug: () => undefined,
                logError: () => undefined,
                Prefs: {},
              },
            },
          },
        ],
      }),
    ).toBeNull();
  });
});
