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
const TOOLS_MENU_ID = "agt-sciagent-tools-menu";
const TOOLS_MENU_SEPARATOR_ID = "agt-sciagent-tools-separator";

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
  private windowObserver: object | null = null;

  install(_data: BootstrapData, _reason: number): void {}

  startup(data: BootstrapData, _reason: number): void {
    Zotero.debug("[SciAgent] Starting add-on...");
    try {
      this.rootURI = data.rootURI;
      Zotero.debug(`[SciAgent] Root URI: ${this.rootURI}`);

      // Insert FTL into every existing window BEFORE registering the item pane
      // section. Zotero renders the section header immediately on registerSection,
      // so the FTL must already be loaded or the l10nID resolves to empty text
      // and the section header is invisible.
      const mainWindows = Zotero.getMainWindows();
      Zotero.debug(`[SciAgent] Pre-loading FTL for ${mainWindows.length} existing window(s)`);
      for (const win of mainWindows) {
        this.insertFTL(win);
      }

      // Register components with error isolation
      this.registerPreferencePane();
      this.registerItemPaneSection();
      this.registerWindowObserver();

      // Full window attachment (styles, Tools menu) for existing windows
      Zotero.debug(`[SciAgent] Found ${mainWindows.length} existing main windows`);
      for (const window of mainWindows) {
        this.onMainWindowLoad({ window });
      }

      Zotero.debug("[SciAgent] Startup complete");
    } catch (error) {
      Zotero.debug(`[SciAgent] FATAL: Startup failed: ${error}`);
      Zotero.logError(error);
    }
  }

  shutdown(_data: BootstrapData, _reason: number): void {
    try {
      Zotero.debug("[SciAgent] Shutting down runtime...");
      this.unregisterWindowObserver();

      if (this.sectionRegistrationId !== null) {
        Zotero.debug(`[SciAgent] Unregistering item pane section: ${this.sectionRegistrationId}`);
        Zotero.ItemPaneManager.unregisterSection(this.sectionRegistrationId);
        this.sectionRegistrationId = null;
      }

      if (typeof Zotero.PreferencePanes.unregister === "function") {
        Zotero.debug("[SciAgent] Unregistering preference pane");
        Zotero.PreferencePanes.unregister(PLUGIN_ID);
      }
      this.preferencePaneRegistered = false;

      Zotero.debug(`[SciAgent] Unmounting ${this.mountedRoots.size} React roots`);
      for (const root of this.mountedRoots.values()) {
        root.unmount();
      }
      this.mountedRoots.clear();

      const mainWindows = Zotero.getMainWindows();
      Zotero.debug(`[SciAgent] Removing assets from ${mainWindows.length} windows`);
      for (const window of mainWindows) {
        this.removeWindowAssets(window);
      }
      Zotero.debug("[SciAgent] Runtime shutdown complete");
    } catch (error) {
      Zotero.debug(`[SciAgent] Error during runtime shutdown: ${error}`);
      Zotero.logError(error);
    }
  }

  uninstall(_data: BootstrapData, _reason: number): void {}

  onMainWindowLoad({ window }: { window: ZoteroWindow }): void {
    try {
      Zotero.debug("[SciAgent] Attaching to main window...");
      Zotero.debug(`[SciAgent] Window location: ${window.location?.href ?? "unknown"}`);
      Zotero.debug(`[SciAgent] Document ready state: ${window.document?.readyState ?? "unknown"}`);

      // Wait for document to be fully ready if needed
      if (window.document.readyState !== "complete") {
        Zotero.debug("[SciAgent] Document not ready, waiting for load event...");
        window.addEventListener(
          "load",
          () => {
            Zotero.debug("[SciAgent] Window load event fired, retrying attachment");
            this.attachToWindow(window);
          },
          { once: true },
        );
        return;
      }

      this.attachToWindow(window);
    } catch (error) {
      Zotero.debug(`[SciAgent] Failed to attach to window: ${error}`);
      Zotero.logError(error);
    }
  }

  private insertFTL(window: ZoteroWindow): void {
    // insertFTLIfNeeded returns a Promise; use .catch() to handle async rejection.
    // A sync try/catch silently misses the rejection and produces
    // "Uncaught (in promise) undefined" in the console.
    const result = window.MozXULElement?.insertFTLIfNeeded("agt/agt.ftl");
    if (result instanceof Promise) {
      result.catch((ftlError: unknown) => {
        Zotero.debug(`[SciAgent] WARNING: FTL insertion failed (non-fatal): ${ftlError}`);
      });
    }
  }

  private attachToWindow(window: ZoteroWindow): void {
    try {
      // FTL was already inserted for existing windows in startup(); this handles
      // new windows that open after the add-on has started.
      Zotero.debug("[SciAgent] Inserting FTL locale...");
      this.insertFTL(window);

      Zotero.debug("[SciAgent] Ensuring window styles...");
      this.ensureWindowStyles(window);

      Zotero.debug("[SciAgent] Adding Tools menu item...");
      this.addToolsMenuItem(window);

      Zotero.debug("[SciAgent] Window attachment complete");
    } catch (error) {
      Zotero.debug(`[SciAgent] Error during window attachment: ${error}`);
      Zotero.logError(error);
    }
  }

  onMainWindowUnload({ window }: { window: ZoteroWindow }): void {
    this.removeWindowAssets(window);
  }

  private ensureWindowStyles(window: ZoteroWindow): void {
    try {
      const document = window.document;
      if (document.getElementById(SECTION_STYLESHEET_ID) !== null) {
        Zotero.debug("[SciAgent] Window styles already present");
        return;
      }

      const styleLink = document.createElement("link");
      styleLink.id = SECTION_STYLESHEET_ID;
      styleLink.rel = "stylesheet";
      styleLink.href = `${this.rootURI}chrome/content/bootstrap-runtime.css`;

      const target = document.head ?? document.documentElement;
      target.appendChild(styleLink);
      Zotero.debug(`[SciAgent] Stylesheet added: ${styleLink.href}`);
    } catch (error) {
      Zotero.debug(`[SciAgent] Failed to add stylesheet: ${error}`);
    }
  }

  private registerPreferencePane(): void {
    if (this.preferencePaneRegistered) {
      Zotero.debug("[SciAgent] Preference pane already registered");
      return;
    }

    try {
      Zotero.debug("[SciAgent] Registering preference pane...");
      if (typeof Zotero.PreferencePanes?.register !== "function") {
        Zotero.debug("[SciAgent] WARNING: Zotero.PreferencePanes.register not available");
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
      Zotero.debug("[SciAgent] Preference pane registered successfully");
    } catch (error) {
      Zotero.debug(`[SciAgent] Failed to register preference pane: ${error}`);
      Zotero.logError(error);
    }
  }

  private registerItemPaneSection(): void {
    if (this.sectionRegistrationId !== null) {
      Zotero.debug(`[SciAgent] Item pane section already registered: ${this.sectionRegistrationId}`);
      return;
    }

    try {
      Zotero.debug("[SciAgent] Registering item pane section...");
      if (typeof Zotero.ItemPaneManager?.registerSection !== "function") {
        Zotero.debug("[SciAgent] WARNING: Zotero.ItemPaneManager.registerSection not available");
        return;
      }
      this.sectionRegistrationId = Zotero.ItemPaneManager.registerSection({
        header: {
          icon: this.iconPath("16"),
          label: "SciAgent",
          l10nID: "agt-item-pane-header",
        },
        onRender: ({ body }) => {
          try {
            this.renderSection(body);
          } catch (error) {
            Zotero.debug(`[SciAgent] Error rendering section: ${error}`);
            Zotero.logError(error);
          }
        },
        paneID: SECTION_ID,
        pluginID: PLUGIN_ID,
        sidenav: {
          icon: this.iconPath("20"),
          label: "SciAgent",
          l10nID: "agt-item-pane-header",
        },
      });

      if (this.sectionRegistrationId) {
        Zotero.debug(`[SciAgent] Item pane section registered successfully: ${this.sectionRegistrationId}`);
      } else {
        Zotero.debug("[SciAgent] WARNING: Item pane registration returned null/empty ID");
      }
    } catch (error) {
      Zotero.debug(`[SciAgent] Failed to register item pane section: ${error}`);
      Zotero.logError(error);
    }
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
    this.removeToolsMenuItem(window);
  }

  private registerWindowObserver(): void {
    if (this.windowObserver !== null) {
      Zotero.debug("[SciAgent] Window observer already registered");
      return;
    }

    try {
      Zotero.debug("[SciAgent] Registering window observer...");
      const self = this;
      this.windowObserver = {
        onOpenWindow(xulWindow: unknown) {
          try {
            Zotero.debug("[SciAgent] Window observer: new window detected");
            const domWindow = (xulWindow as { docShell?: { domWindow?: ZoteroWindow } }).docShell?.domWindow;
            if (domWindow === undefined) {
              Zotero.debug("[SciAgent] Window observer: domWindow is undefined");
              return;
            }

            domWindow.addEventListener(
              "load",
              function onLoad() {
                domWindow.removeEventListener("load", onLoad);
                Zotero.debug(`[SciAgent] Window observer: window loaded - ${domWindow.location?.href ?? "unknown"}`);
                if (domWindow.location.href === "chrome://zotero/content/zoteroPane.xhtml") {
                  Zotero.debug("[SciAgent] Window observer: detected main Zotero pane, attaching");
                  self.onMainWindowLoad({ window: domWindow });
                } else {
                  Zotero.debug("[SciAgent] Window observer: not a main window, ignoring");
                }
              },
              false,
            );
          } catch (error) {
            Zotero.debug(`[SciAgent] Window observer error in onOpenWindow: ${error}`);
            Zotero.logError(error);
          }
        },

        onCloseWindow() {},
      };

      Services.wm.addListener(this.windowObserver);
      Zotero.debug("[SciAgent] Window observer registered successfully");
    } catch (error) {
      Zotero.debug(`[SciAgent] Failed to register window observer: ${error}`);
      Zotero.logError(error);
    }
  }

  private unregisterWindowObserver(): void {
    if (this.windowObserver === null) {
      return;
    }

    try {
      Zotero.debug("[SciAgent] Unregistering window observer");
      Services.wm.removeListener(this.windowObserver);
      this.windowObserver = null;
    } catch (error) {
      Zotero.debug(`[SciAgent] Error unregistering window observer: ${error}`);
    }
  }

  private addToolsMenuItem(window: ZoteroWindow): void {
    try {
      const document = window.document;

      if (document.getElementById(TOOLS_MENU_ID) !== null) {
        Zotero.debug("[SciAgent] Tools menu item already exists");
        return;
      }

      const toolsPopup = document.getElementById("menu_ToolsPopup");
      if (toolsPopup === null) {
        Zotero.debug("[SciAgent] WARNING: menu_ToolsPopup not found in window");
        Zotero.debug(`[SciAgent] Available element IDs: ${Array.from(document.querySelectorAll("[id]")).map(el => el.id).join(", ")}`);

        // Try again after a short delay in case the menu isn't ready yet
        setTimeout(() => {
          Zotero.debug("[SciAgent] Retrying Tools menu attachment...");
          const retryPopup = document.getElementById("menu_ToolsPopup");
          if (retryPopup) {
            this.attachToolsMenuItems(window, retryPopup);
          } else {
            Zotero.debug("[SciAgent] ERROR: menu_ToolsPopup still not found after retry");
          }
        }, 1000);
        return;
      }

      this.attachToolsMenuItems(window, toolsPopup);
    } catch (error) {
      Zotero.debug(`[SciAgent] Failed to add Tools menu item: ${error}`);
      Zotero.logError(error);
    }
  }

  private attachToolsMenuItems(window: ZoteroWindow, toolsPopup: Element): void {
    try {
      const document = window.document;

      // Check again if already added
      if (document.getElementById(TOOLS_MENU_ID) !== null) {
        Zotero.debug("[SciAgent] Tools menu item already exists (duplicate check)");
        return;
      }

      const separator = document.createXULElement("menuseparator");
      separator.id = TOOLS_MENU_SEPARATOR_ID;

      const menuitem = document.createXULElement("menuitem");
      menuitem.id = TOOLS_MENU_ID;
      menuitem.setAttribute("label", "SciAgent");
      menuitem.setAttribute("data-l10n-id", "agt-tools-menu-label");
      menuitem.addEventListener("command", () => {
        this.handleToolsMenuCommand(window);
      });

      toolsPopup.appendChild(separator);
      toolsPopup.appendChild(menuitem);
      Zotero.debug("[SciAgent] Tools menu item added successfully");
    } catch (error) {
      Zotero.debug(`[SciAgent] Failed to attach Tools menu items: ${error}`);
      Zotero.logError(error);
    }
  }

  private removeToolsMenuItem(window: ZoteroWindow): void {
    window.document.getElementById(TOOLS_MENU_ID)?.remove();
    window.document.getElementById(TOOLS_MENU_SEPARATOR_ID)?.remove();
  }

  private handleToolsMenuCommand(window: ZoteroWindow): void {
    try {
      Zotero.debug("[SciAgent] Tools menu command triggered — opening main panel");
      this.openOrFocusMainPanel(window);
    } catch (error) {
      Zotero.debug(`[SciAgent] Error handling Tools menu command: ${error}`);
      Zotero.logError(error);
    }
  }

  private openOrFocusMainPanel(window: ZoteroWindow): void {
    // Focus the existing panel if it is already open.
    const existing = Services.wm.getMostRecentWindow("agt:main-panel");
    if (existing !== null) {
      Zotero.debug("[SciAgent] Main panel already open — focusing");
      (existing as { focus?: () => void }).focus?.();
      return;
    }

    Zotero.debug("[SciAgent] Opening main panel window");
    const panelUrl = "chrome://agt/content/sciagent-panel.xhtml";
    const bundleUrl = `${this.rootURI}chrome/content/panel-entry.js`;

    const panelWin = window.openDialog?.(
      panelUrl,
      "_blank",
      "chrome,dialog=no,resizable,width=720,height=820,centerscreen",
    );

    if (!panelWin) {
      Zotero.debug("[SciAgent] Failed to open main panel window — openDialog returned null");
      return;
    }

    panelWin.addEventListener(
      "load",
      () => {
        try {
          Zotero.debug("[SciAgent] Loading panel-entry bundle into panel window");
          Services.scriptloader.loadSubScript(bundleUrl, panelWin);
          const scopedWin = panelWin as unknown as { SciAgentPanel?: { init(): void } };
          if (typeof scopedWin.SciAgentPanel?.init === "function") {
            scopedWin.SciAgentPanel.init();
            Zotero.debug("[SciAgent] Main panel React app mounted");
          } else {
            Zotero.debug("[SciAgent] WARNING: SciAgentPanel.init not found after bundle load");
          }
        } catch (err) {
          Zotero.debug(`[SciAgent] Error mounting main panel React app: ${err}`);
          Zotero.logError(err);
        }
      },
      { once: true },
    );
  }

  private iconPath(size: "16" | "20" | "48" | "96"): string {
    return `${this.rootURI}icons/${size}/agt.svg`;
  }
}

export function createRuntimeController(): RuntimeController {
  return new RuntimeController();
}
