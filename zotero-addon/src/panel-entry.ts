import { createElement } from "react";
import { createRoot, type Root } from "react-dom/client";

import { createBackendClient } from "./client/backendClient";
import { resolvePanelZotero, type PanelBridgeTarget } from "./host/panelBridge";
import { createZoteroPreferenceStore } from "./host/prefs";
import type { ZoteroGlobal } from "./host/zoteroTypes";
import { App } from "./ui/App";
import type { AddonUiServices } from "./ui/serviceTypes";

type PanelWindow = Window &
  typeof globalThis & {
    SciAgentPanel?: {
      init(): void;
    };
  } & PanelBridgeTarget;

let panelRoot: Root | null = null;
let panelInitialized = false;

function getPanelWindow(): PanelWindow {
  return globalThis as unknown as PanelWindow;
}

function resolveZotero(): ZoteroGlobal | null {
  return resolvePanelZotero(getPanelWindow());
}

function renderStartupError(message: string): void {
  const mountPoint = document.getElementById("agt-panel-root");
  if (mountPoint === null) {
    document.body.replaceChildren();
    const fallback = document.createElement("div");
    fallback.className = "agt-panel-startup-error";
    fallback.textContent = message;
    document.body.appendChild(fallback);
    return;
  }

  mountPoint.replaceChildren();
  const fallback = document.createElement("div");
  fallback.className = "agt-panel-startup-error";
  fallback.textContent = message;
  mountPoint.appendChild(fallback);
}

function createPanelServices(zotero: ZoteroGlobal): AddonUiServices {
  const preferenceStore = createZoteroPreferenceStore(zotero);

  return {
    createClient(config) {
      return createBackendClient({
        apiKey: config.apiKey,
        baseUrl: config.backendUrl,
        clientId: config.clientId,
        fetchImpl: globalThis.fetch.bind(globalThis),
        zoteroApiKey: config.zoteroApiKey,
        zoteroLibraryId: config.zoteroLibraryId,
        zoteroLibraryType: config.zoteroLibraryType,
        useCustomLlm: config.useCustomLlm,
        customLlmProvider: config.customLlmProvider,
        customLlmBaseUrl: config.customLlmBaseUrl,
        customLlmModel: config.customLlmModel,
        customLlmApiKey: config.customLlmApiKey,
      });
    },

    async loadConfig() {
      return preferenceStore.readConfig();
    },

    log(message, data) {
      if (data === undefined) {
        zotero.debug(`[SciAgent Panel] ${message}`);
        return;
      }
      try {
        zotero.debug(`[SciAgent Panel] ${message}: ${JSON.stringify(data)}`);
      } catch {
        zotero.debug(`[SciAgent Panel] ${message}: [unserializable payload]`);
      }
    },

    async saveConfig(update) {
      return preferenceStore.writeConfig(update);
    },
  };
}

declare global {
  interface Window {
    SciAgentPanel?: {
      init(): void;
    };
  }
}

function initPanel(): void {
  const zotero = resolveZotero();
  if (zotero === null) {
    renderStartupError("SciAgent could not access the Zotero host API. Reopen the panel from Zotero Tools > SciAgent.");
    return;
  }

  if (panelInitialized) {
    return;
  }

  try {
    const mountPoint = document.getElementById("agt-panel-root");
    if (mountPoint === null) {
      zotero.debug("[SciAgent Panel] Mount point #agt-panel-root not found");
      renderStartupError("SciAgent could not find its panel mount point.");
      return;
    }

    if (panelRoot === null) {
      panelRoot = createRoot(mountPoint);
    }

    const services = createPanelServices(zotero);
    panelRoot.render(createElement(App, { services }));
    panelInitialized = true;
    zotero.debug("[SciAgent Panel] Main-window React app mounted");
  } catch (error) {
    zotero.debug(`[SciAgent Panel] Startup failed: ${error instanceof Error ? error.message : String(error)}`);
    zotero.logError(error);
    renderStartupError("SciAgent UI failed to start. Check the Zotero Error Console for [SciAgent Panel] details.");
  }
}

function initWhenReady(): void {
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initPanel, { once: true });
    return;
  }

  initPanel();
}

getPanelWindow().SciAgentPanel = {
  init(): void {
    initPanel();
  },
};

initWhenReady();
