import type { ZoteroGlobal } from "./zoteroTypes";

export const PANEL_BRIDGE_PROPERTY = "__SciAgentPanelBridge";

export interface PanelBridgePayload {
  Zotero: ZoteroGlobal;
  wrappedJSObject: PanelBridgePayload;
}

export type PanelBridgeTarget = {
  Zotero?: unknown;
  arguments?: unknown;
  opener?: unknown;
  wrappedJSObject?: unknown;
} & Partial<Record<typeof PANEL_BRIDGE_PROPERTY, unknown>>;

function isObjectLike(value: unknown): value is Record<PropertyKey, unknown> {
  return (typeof value === "object" && value !== null) || typeof value === "function";
}

function readProperty(source: unknown, property: PropertyKey): unknown {
  if (!isObjectLike(source)) {
    return undefined;
  }

  try {
    return source[property];
  } catch {
    return undefined;
  }
}

function firstWindowArgument(args: unknown): unknown {
  if (Array.isArray(args)) {
    return args[0];
  }

  const length = readProperty(args, "length");
  if (typeof length === "number" && length > 0) {
    return readProperty(args, 0);
  }

  return undefined;
}

export function isZoteroGlobal(value: unknown): value is ZoteroGlobal {
  const prefs = readProperty(value, "Prefs");

  return (
    isObjectLike(value) &&
    typeof readProperty(value, "debug") === "function" &&
    typeof readProperty(value, "logError") === "function" &&
    isObjectLike(prefs) &&
    typeof readProperty(prefs, "get") === "function" &&
    typeof readProperty(prefs, "set") === "function"
  );
}

function unwrapCandidate(candidate: unknown): unknown {
  return readProperty(candidate, "wrappedJSObject") ?? candidate;
}

function resolveZoteroCandidate(candidate: unknown): ZoteroGlobal | null {
  const unwrapped = unwrapCandidate(candidate);
  if (isZoteroGlobal(unwrapped)) {
    return unwrapped;
  }

  const candidateZotero = readProperty(unwrapped, "Zotero");
  if (isZoteroGlobal(candidateZotero)) {
    return candidateZotero;
  }

  return null;
}

function cacheZotero(panelWindow: PanelBridgeTarget, zotero: ZoteroGlobal): void {
  try {
    panelWindow.Zotero = zotero;
  } catch {
    // Cross-compartment wrappers can reject writes; the original bridge remains valid.
  }

  const rawPanelWindow = readProperty(panelWindow, "wrappedJSObject");
  if (isObjectLike(rawPanelWindow)) {
    try {
      rawPanelWindow.Zotero = zotero;
    } catch {
      // Best-effort cache only.
    }
  }
}

function resolveFromCandidateList(candidates: unknown[]): ZoteroGlobal | null {
  for (const candidate of candidates) {
    const zotero = resolveZoteroCandidate(candidate);
    if (zotero !== null) {
      return zotero;
    }
  }

  return null;
}

export function createPanelBridge(zotero: ZoteroGlobal): PanelBridgePayload {
  const bridge = { Zotero: zotero } as PanelBridgePayload;
  bridge.wrappedJSObject = bridge;
  return bridge;
}

export function installPanelBridge(target: PanelBridgeTarget, bridge: PanelBridgePayload): void {
  target[PANEL_BRIDGE_PROPERTY] = bridge;
  target.Zotero = bridge.Zotero;
}

export function resolvePanelZotero(panelWindow: PanelBridgeTarget): ZoteroGlobal | null {
  const rawPanelWindow = readProperty(panelWindow, "wrappedJSObject");
  const firstArgument = firstWindowArgument(readProperty(panelWindow, "arguments"));
  const rawFirstArgument = firstWindowArgument(readProperty(rawPanelWindow, "arguments"));
  const opener = readProperty(panelWindow, "opener");
  const rawPanelOpener = readProperty(rawPanelWindow, "opener");
  const rawOpener = readProperty(opener, "wrappedJSObject");
  const rawPanelRawOpener = readProperty(rawPanelOpener, "wrappedJSObject");

  const zotero = resolveFromCandidateList([
    readProperty(panelWindow, "Zotero"),
    readProperty(panelWindow, PANEL_BRIDGE_PROPERTY),
    readProperty(rawPanelWindow, "Zotero"),
    readProperty(rawPanelWindow, PANEL_BRIDGE_PROPERTY),
    firstArgument,
    rawFirstArgument,
    readProperty(opener, "Zotero"),
    readProperty(opener, PANEL_BRIDGE_PROPERTY),
    readProperty(rawOpener, "Zotero"),
    readProperty(rawOpener, PANEL_BRIDGE_PROPERTY),
    readProperty(rawPanelOpener, "Zotero"),
    readProperty(rawPanelOpener, PANEL_BRIDGE_PROPERTY),
    readProperty(rawPanelRawOpener, "Zotero"),
    readProperty(rawPanelRawOpener, PANEL_BRIDGE_PROPERTY),
  ]);

  if (zotero !== null) {
    cacheZotero(panelWindow, zotero);
  }

  return zotero;
}
