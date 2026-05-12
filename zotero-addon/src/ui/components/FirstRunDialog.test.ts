import { describe, expect, it, vi } from "vitest";

import { SCIAGENT_SERVER_VERSION } from "../../host/serverManager";
import type { AddonUiServices } from "../serviceTypes";

function makeServices(overrides?: Partial<AddonUiServices>): AddonUiServices {
  return {
    createClient: vi.fn(),
    loadConfig: vi.fn(),
    log: vi.fn(),
    saveConfig: vi.fn(),
    ...overrides,
  };
}

describe("SCIAGENT_SERVER_VERSION", () => {
  it("is a non-empty semver string", () => {
    expect(SCIAGENT_SERVER_VERSION).toMatch(/^\d+\.\d+\.\d+$/);
  });
});

describe("AddonUiServices binary contract", () => {
  it("download + start service methods round-trip correctly", async () => {
    const progressCalls: number[] = [];
    const services = makeServices({
      checkBinaryInstalled: vi.fn().mockResolvedValue(false),
      downloadBinary: vi.fn().mockImplementation(
        async (_version: string, onProgress: (pct: number) => void) => {
          onProgress(50);
          onProgress(100);
        },
      ),
      startServerAfterDownload: vi.fn().mockResolvedValue(undefined),
    });

    const installed = await services.checkBinaryInstalled?.();
    expect(installed).toBe(false);

    await services.downloadBinary?.(SCIAGENT_SERVER_VERSION, (pct) => {
      progressCalls.push(pct);
    });
    expect(progressCalls).toEqual([50, 100]);

    await services.startServerAfterDownload?.();
    expect(services.startServerAfterDownload).toHaveBeenCalledOnce();
  });

  it("checkBinaryInstalled returns true when binary is present", async () => {
    const services = makeServices({
      checkBinaryInstalled: vi.fn().mockResolvedValue(true),
    });
    expect(await services.checkBinaryInstalled?.()).toBe(true);
  });

  it("optional methods are absent in minimal service stub", () => {
    const services = makeServices();
    expect(services.checkBinaryInstalled).toBeUndefined();
    expect(services.downloadBinary).toBeUndefined();
    expect(services.startServerAfterDownload).toBeUndefined();
  });
});
