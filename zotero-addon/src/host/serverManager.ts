/**
 * Lifecycle manager for the embedded SciAgent server binary (SCI-0604).
 *
 * Handles platform detection, binary path resolution, download-on-first-run,
 * process spawning, health polling, and graceful shutdown.
 */

import { collectProviderEnv } from "./prefs";
import type { AddonConfig } from "./prefs";

export class ServerStartError extends Error {
  constructor(
    public readonly reason: "timeout" | "binary_missing" | "port_unavailable",
    message: string,
  ) {
    super(message);
    this.name = "ServerStartError";
  }
}

// Zotero XPCOM / platform globals — declared here so TypeScript resolves them.
declare const Services: {
  appinfo: { OS: string; XPCOMABI: string };
  dirsvc: { get(name: string, iface: unknown): { path: string } };
};
declare const Ci: { nsIFile: unknown };
declare const PathUtils: { join(...parts: string[]): string };
declare const IOUtils: {
  stat(path: string): Promise<unknown>;
  makeDirectory(path: string, options?: { createAncestors?: boolean }): Promise<void>;
  write(path: string, data: Uint8Array): Promise<void>;
  move(from: string, to: string): Promise<void>;
};
declare const Subprocess: {
  call(options: {
    command: string;
    arguments?: string[];
    environment?: Record<string, string>;
    stderr?: string;
  }): Promise<{ kill(): void }>;
};

export const SCIAGENT_SERVER_VERSION = "0.2.0";

const SERVER_PORT_DEFAULT = 57321;
const SERVER_PORTS = [57321, 57322, 57323, 57324, 57325];
let _resolvedPort = SERVER_PORT_DEFAULT;

function _healthUrl(port: number): string {
  return `http://127.0.0.1:${port}/health`;
}

function _getPlatform(): string {
  const os = Services.appinfo.OS;
  const cpu = Services.appinfo.XPCOMABI;
  if (os === "WINNT") return "windows-x64";
  if (os === "Darwin") return cpu.startsWith("aarch64") ? "macos-arm64" : "macos-x86_64";
  return "linux-x86_64";
}

function _getBinaryName(): string {
  const plat = _getPlatform();
  return plat.startsWith("windows") ? `sciagent-server-${plat}.exe` : `sciagent-server-${plat}`;
}

function _getDataDir(): string {
  return PathUtils.join(Services.dirsvc.get("Home", Ci.nsIFile).path, ".sciagent");
}

function _getBinDir(): string {
  return PathUtils.join(_getDataDir(), "bin");
}

export async function getBinaryPath(): Promise<string> {
  return PathUtils.join(_getBinDir(), _getBinaryName());
}

export async function binaryInstalled(): Promise<boolean> {
  try {
    await IOUtils.stat(await getBinaryPath());
    return true;
  } catch {
    return false;
  }
}

export async function downloadBinary(
  version: string,
  onProgress: (pct: number) => void,
): Promise<void> {
  const name = _getBinaryName();
  const url = `https://github.com/AdamKrysztopa/sciagent/releases/download/v${version}/${name}`;
  const binDir = _getBinDir();
  await IOUtils.makeDirectory(binDir, { createAncestors: true });
  const tmpPath = PathUtils.join(binDir, `${name}.tmp`);

  await new Promise<void>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("GET", url);
    xhr.responseType = "arraybuffer";
    xhr.onprogress = (e: ProgressEvent) => {
      if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100));
    };
    xhr.onload = () => {
      if (xhr.status !== 200) {
        reject(new Error(`HTTP ${xhr.status}`));
        return;
      }
      void IOUtils.write(tmpPath, new Uint8Array(xhr.response as ArrayBuffer)).then(resolve);
    };
    xhr.onerror = () => reject(new Error("Network error during download"));
    xhr.send();
  });

  if (_getPlatform() !== "windows-x64") {
    await Subprocess.call({ command: "/bin/chmod", arguments: ["+x", tmpPath] });
  }
  await IOUtils.move(tmpPath, await getBinaryPath());
}

let _proc: { kill(): void } | null = null;

async function _isPortFree(port: number): Promise<boolean> {
  try {
    await fetch(`http://127.0.0.1:${port}`, { signal: AbortSignal.timeout(100) });
    return false;
  } catch {
    return true;
  }
}

async function _findFreePort(): Promise<number> {
  for (const port of SERVER_PORTS) {
    if (await _isPortFree(port)) return port;
  }
  throw new ServerStartError("port_unavailable", "No free port found for SciAgent server");
}

export async function isServerRunning(): Promise<boolean> {
  try {
    const r = await fetch(_healthUrl(_resolvedPort), { signal: AbortSignal.timeout(500) });
    return r.ok;
  } catch {
    return false;
  }
}

export async function startServer(config: AddonConfig): Promise<void> {
  if (await isServerRunning()) return;

  _resolvedPort = await _findFreePort();
  const binPath = await getBinaryPath();

  let binExists = false;
  try {
    binExists = await IOUtils.stat(binPath).then(() => true);
  } catch {
    binExists = false;
  }
  if (!binExists) {
    throw new ServerStartError("binary_missing", `SciAgent server binary not found at: ${binPath}`);
  }

  const dataDir = _getDataDir();

  _proc = await Subprocess.call({
    command: binPath,
    arguments: ["--port", String(_resolvedPort), "--data-dir", dataDir],
    environment: collectProviderEnv(config),
    stderr: "pipe",
  });

  const deadline = Date.now() + 15_000;
  while (Date.now() < deadline) {
    if (await isServerRunning()) return;
    await new Promise((r) => setTimeout(r, 300));
  }
  throw new ServerStartError("timeout", "SciAgent server did not respond to health checks within 15 seconds");
}

export async function stopServer(): Promise<void> {
  if (_proc) {
    try {
      _proc.kill();
    } catch {
      /* already dead */
    }
    _proc = null;
  }
}

export function getResolvedPort(): number {
  return _resolvedPort;
}
