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
  };
  onRender(context: { body: HTMLElement; editable?: boolean; item?: unknown; tabType?: string }): void;
  paneID: string;
  pluginID: string;
  sidenav: {
    icon: string;
    l10nID: string;
  };
}

export interface ItemPaneManager {
  registerSection(definition: ItemPaneSectionDefinition): string;
  unregisterSection(id: string): void;
}

export interface ZoteroWindow extends Window {
  MozXULElement?: {
    insertFTLIfNeeded(href: string): void;
  };
}

export interface ZoteroGlobal {
  ItemPaneManager: ItemPaneManager;
  PreferencePanes: PreferencePaneManager;
  Prefs: ZoteroPrefs;
  debug(message: string): void;
  getMainWindows(): ZoteroWindow[];
}

declare global {
  const Zotero: ZoteroGlobal;
}
