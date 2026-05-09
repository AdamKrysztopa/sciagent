export interface BootstrapData {
  id?: string;
  resourceURI?: { spec: string };
  rootURI: string;
  version?: string;
}

export interface ZoteroPrefs {
  get(key: string, global?: boolean): unknown;
  set(key: string, value: string | boolean | number, global?: boolean): void;
}

export interface PreferencePaneDefinition {
  image?: string;
  label?: string;
  pluginID: string;
  scripts?: string[];
  src: string;
  stylesheets?: string[];
}

export interface PreferencePaneManager {
  register(definition: PreferencePaneDefinition): void;
  unregister?(pluginID: string): void;
}

export interface ItemPaneSectionDefinition {
  header: {
    icon: string;
    l10nID: string;
    label?: string; // Optional fallback when FTL is unavailable
  };
  onRender(context: { body: HTMLElement; editable?: boolean; item?: unknown; tabType?: string }): void;
  paneID: string;
  pluginID: string;
  sidenav: {
    icon: string;
    l10nID: string;
    label?: string; // Optional fallback when FTL is unavailable
  };
}

export interface ItemPaneManager {
  registerSection(definition: ItemPaneSectionDefinition): string;
  unregisterSection(id: string): void;
}

export interface ZoteroWindow extends Window {
  MozXULElement?: {
    insertFTLIfNeeded(href: string): Promise<void>;
  };
  document: Document & {
    createXULElement(tagName: string): Element;
  };
  openDialog?(url: string, name: string, features: string, ...args: unknown[]): Window;
}

export interface ZoteroGlobal {
  ItemPaneManager: ItemPaneManager;
  PreferencePanes: PreferencePaneManager;
  Prefs: ZoteroPrefs;
  debug(message: string): void;
  getMainWindows(): ZoteroWindow[];
  logError(error: unknown): void;
}

export interface WindowMediator {
  addListener(listener: object): void;
  getMostRecentWindow(windowType: string): Window | null;
  removeListener(listener: object): void;
}

export interface PromptService {
  alert(parent: Window | null, dialogTitle: string, text: string): void;
}

export interface ScriptLoader {
  loadSubScript(url: string, target?: object): void;
}

export interface ServicesGlobal {
  prompt: PromptService;
  scriptloader: ScriptLoader;
  wm: WindowMediator;
}

declare global {
  const Zotero: ZoteroGlobal;
  const Services: ServicesGlobal;
}
