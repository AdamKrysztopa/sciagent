import { createElement } from "react";
import { createRoot, type Root } from "react-dom/client";

import { createBackendClient } from "../client/backendClient";
import { App } from "../ui/App";
import type { AddonUiServices } from "../ui/serviceTypes";
import { createZoteroPreferenceStore } from "./prefs";
import type { BootstrapData, ZoteroWindow } from "./zoteroTypes";

const PLUGIN_ID = "agt@yourdomain.org";
const SECTION_ID = "agt-sciagent-pane";
const SECTION_STYLESHEET_ID = "agt-sciagent-section-style";

function createUiServices(): AddonUiServices {
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
        Zotero.debug(`[SciAgent] ${message}`);
        return;
      }

      try {
        Zotero.debug(`[SciAgent] ${message}: ${JSON.stringify(data)}`);
      } catch {
        Zotero.debug(`[SciAgent] ${message}: [unserializable payload]`);
      }
    },

    async saveConfig(update) {
      return preferenceStore.writeConfig(update);
    },
  };
}

export class RuntimeController {
  private readonly mountedRoots = new Map<HTMLElement, Root>();
  private readonly services = createUiServices();

  private rootURI = "";
  private sectionRegistrationId: string | null = null;
  private preferencePaneRegistered = false;

  install(_data: BootstrapData, _reason: number): void {}

  startup(data: BootstrapData, _reason: number): void {
    this.rootURI = data.rootURI;
    this.registerPreferencePane();
    this.registerItemPaneSection();

    for (const window of Zotero.getMainWindows()) {
      this.onMainWindowLoad({ window });
    }
  }

  shutdown(_data: BootstrapData, _reason: number): void {
    if (this.sectionRegistrationId !== null) {
      Zotero.ItemPaneManager.unregisterSection(this.sectionRegistrationId);
      this.sectionRegistrationId = null;
    }

    if (typeof Zotero.PreferencePanes.unregister === "function") {
      Zotero.PreferencePanes.unregister(PLUGIN_ID);
    }
    this.preferencePaneRegistered = false;

    for (const root of this.mountedRoots.values()) {
      root.unmount();
    }
    this.mountedRoots.clear();

    for (const window of Zotero.getMainWindows()) {
      this.removeWindowAssets(window);
    }
  }

  uninstall(_data: BootstrapData, _reason: number): void {}

  onMainWindowLoad({ window }: { window: ZoteroWindow }): void {
    window.MozXULElement?.insertFTLIfNeeded("agt.ftl");
    this.ensureWindowStyles(window);
  }

  onMainWindowUnload({ window }: { window: ZoteroWindow }): void {
    this.removeWindowAssets(window);
  }

  private ensureWindowStyles(window: ZoteroWindow): void {
    const document = window.document;
    if (document.getElementById(SECTION_STYLESHEET_ID) !== null) {
      return;
    }

    const styleLink = document.createElement("link");
    styleLink.id = SECTION_STYLESHEET_ID;
    styleLink.rel = "stylesheet";
    styleLink.href = `${this.rootURI}chrome/content/bootstrap-runtime.css`;

    const target = document.head ?? document.documentElement;
    target.appendChild(styleLink);
  }

  private registerPreferencePane(): void {
    if (this.preferencePaneRegistered) {
      return;
    }

    Zotero.PreferencePanes.register({
      image: this.iconPath("48"),
      label: "SciAgent",
      pluginID: PLUGIN_ID,
      scripts: ["chrome/content/preferences-pane.js"],
      src: "preferences.xhtml",
      stylesheets: ["chrome/content/preferences-pane.css"],
    });

    this.preferencePaneRegistered = true;
  }

  private registerItemPaneSection(): void {
    if (this.sectionRegistrationId !== null) {
      return;
    }

    this.sectionRegistrationId = Zotero.ItemPaneManager.registerSection({
      header: {
        icon: this.iconPath("16"),
        l10nID: "agt-item-pane-header",
      },
      onRender: ({ body }) => {
        this.renderSection(body);
      },
      paneID: SECTION_ID,
      pluginID: PLUGIN_ID,
      sidenav: {
        icon: this.iconPath("20"),
        l10nID: "agt-item-pane-header",
      },
    });
  }

  private renderSection(body: HTMLElement): void {
    const mountPoint = this.ensureMountPoint(body);
    let root = this.mountedRoots.get(mountPoint);
    if (root === undefined) {
      root = createRoot(mountPoint);
      this.mountedRoots.set(mountPoint, root);
    }

    root.render(createElement(App, { services: this.services }));
  }

  private ensureMountPoint(body: HTMLElement): HTMLElement {
    const existing = body.querySelector<HTMLElement>(".agt-root");
    if (existing !== null) {
      return existing;
    }

    body.replaceChildren();
    const mountPoint = body.ownerDocument.createElement("div");
    mountPoint.className = "agt-root";
    body.appendChild(mountPoint);
    return mountPoint;
  }

  private removeWindowAssets(window: ZoteroWindow): void {
    window.document.getElementById(SECTION_STYLESHEET_ID)?.remove();
  }

  private iconPath(size: "16" | "20" | "48" | "96"): string {
    return `${this.rootURI}icons/${size}/agt.svg`;
  }
}

export function createRuntimeController(): RuntimeController {
  return new RuntimeController();
}
