import type { SciAgentBackendClient } from "../client/backendClient";
import type { NativeWriteResult } from "../host/zoteroWriter";
import type { AddonConfig } from "../host/prefs";
import type { NormalizedPaper } from "../shared/contracts";

export interface AddonUiServices {
  createClient(config: AddonConfig): SciAgentBackendClient;
  loadConfig(): Promise<AddonConfig>;
  log(message: string, data?: unknown): void;
  saveConfig(update: Partial<AddonConfig>): Promise<AddonConfig>;
  /**
   * Perform native Zotero write (ZAP-6/7/8). Present in the real Zotero runtime;
   * undefined in browser/test environments where native write is unsupported.
   */
  nativeWrite?(
    papers: NormalizedPaper[],
    collectionName: string,
    enablePdf: boolean,
  ): Promise<NativeWriteResult>;
}
