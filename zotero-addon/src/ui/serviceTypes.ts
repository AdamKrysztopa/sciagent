import type { SciAgentBackendClient } from "../client/backendClient";
import type { AddonConfig } from "../host/prefs";

export interface AddonUiServices {
  createClient(config: AddonConfig): SciAgentBackendClient;
  loadConfig(): Promise<AddonConfig>;
  log(message: string, data?: unknown): void;
  saveConfig(update: Partial<AddonConfig>): Promise<AddonConfig>;
}
