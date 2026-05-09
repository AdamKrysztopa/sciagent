import { createElement } from "react";
import { createRoot } from "react-dom/client";

import { createBackendClient } from "./client/backendClient";
import { createZoteroPreferenceStore } from "./host/prefs";
import { App } from "./ui/App";
import type { AddonUiServices } from "./ui/serviceTypes";

function createPanelServices(): AddonUiServices {
  const preferenceStore = createZoteroPreferenceStore(Zotero);

  return {
    createClient(config) {
      return createBackendClient({
        apiKey: config.apiKey,
        baseUrl: config.backendUrl,
        clientId: config.clientId,
        fetchImpl: globalThis.fetch.bind(globalThis),
      });
    },

    async loadConfig() {
      return preferenceStore.readConfig();
    },

    log(message, data) {
      if (data === undefined) {
        Zotero.debug(`[SciAgent Panel] ${message}`);
        return;
      }
      try {
        Zotero.debug(`[SciAgent Panel] ${message}: ${JSON.stringify(data)}`);
      } catch {
        Zotero.debug(`[SciAgent Panel] ${message}: [unserializable payload]`);
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

window.SciAgentPanel = {
  init(): void {
    const mountPoint = document.getElementById("agt-panel-root");
    if (mountPoint === null) {
      Zotero.debug("[SciAgent Panel] Mount point #agt-panel-root not found");
      return;
    }
    const services = createPanelServices();
    const root = createRoot(mountPoint);
    root.render(createElement(App, { services }));
    Zotero.debug("[SciAgent Panel] Main-window React app mounted");
  },
};
