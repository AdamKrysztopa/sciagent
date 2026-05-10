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
  Collections: ZoteroCollections;
  Items: ZoteroItems;
  Attachments: ZoteroAttachments;
  Libraries: ZoteroLibraries;
  debug(message: string): void;
  getMainWindows(): ZoteroWindow[];
  logError(error: unknown): void;
}

// --- ZAP-6: Collection management types ---

export interface ZoteroCollection {
  id: number;
  key: string;
  name: string;
  parentKey: string | false;
  libraryID: number;
}

export interface ZoteroCollectionData {
  name: string;
  parentID?: number;
}

export interface ZoteroCollections {
  getByLibrary(libraryID: number, recursive?: boolean): ZoteroCollection[];
  getByParent(parentID: number, recursive?: boolean): ZoteroCollection[];
  add(data: ZoteroCollectionData): Promise<ZoteroCollection>;
  get(id: number): ZoteroCollection | false;
  getAsync(id: number): Promise<ZoteroCollection | false>;
}

// --- ZAP-7: Item management types ---

export interface ZoteroItem {
  id: number;
  key: string;
  libraryID: number;
  getField(field: string): string | number | boolean;
  setField(field: string, value: string | number | boolean): void;
  addToCollection(collectionID: number): void;
  save(): Promise<void>;
}

export interface ZoteroItemCreateData {
  itemType: string;
  title?: string;
  DOI?: string;
  abstractNote?: string;
  year?: number | string;
  url?: string;
  [key: string]: unknown;
}

export interface ZoteroItems {
  getAll(libraryID: number): ZoteroItem[];
  getAsync(id: number): Promise<ZoteroItem | false>;
  get(id: number): ZoteroItem | false;
  add(data: ZoteroItemCreateData, libraryID?: number): Promise<ZoteroItem>;
}

// --- ZAP-8: Attachment management types ---

export interface ZoteroAttachment {
  id: number;
  key: string;
  parentID: number;
}

export interface ZoteroAttachments {
  importFromURL(options: {
    url: string;
    parentItemID: number;
    title?: string;
    fileBaseName?: string;
    contentType?: string;
    referrer?: string;
    libraryID?: number;
    collections?: number[];
  }): Promise<ZoteroAttachment | false>;
}

// --- Library types ---

export interface ZoteroLibrary {
  libraryID: number;
  name: string;
  editable: boolean;
}

export interface ZoteroLibraries {
  getUserLibrary(): ZoteroLibrary;
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
