import AdmZip from "adm-zip";
import { build as esbuild } from "esbuild";
import {
  copyFileSync,
  cpSync,
  mkdirSync,
  readFileSync,
  readdirSync,
  rmSync,
  statSync,
} from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const BUILD_DIR = join(ROOT, "build");
const STAGE_DIR = join(BUILD_DIR, "xpi");
const XPI_PATH = join(BUILD_DIR, "sciagent-zotero-addon.xpi");
const SUPPORTED_ZOTERO_MIN_VERSION = "9.0.0";
const SUPPORTED_ZOTERO_MAX_VERSION = "9.*";

const STATIC_FILES = ["manifest.json", "bootstrap.js", "prefs.js", "preferences.xhtml"];
const STATIC_DIRS = ["icons", "locale"];
// Files that must be served at chrome://agt/content/ and therefore live in chrome/content/
const CHROME_CONTENT_FILES = ["sciagent-panel.html"];

function clean() {
  rmSync(BUILD_DIR, { force: true, recursive: true });
}

function copyStaticAssets() {
  for (const fileName of STATIC_FILES) {
    copyFileSync(join(ROOT, fileName), join(STAGE_DIR, fileName));
  }

  for (const directory of STATIC_DIRS) {
    cpSync(join(ROOT, directory), join(STAGE_DIR, directory), { recursive: true });
  }

  for (const fileName of CHROME_CONTENT_FILES) {
    copyFileSync(join(ROOT, fileName), join(STAGE_DIR, "chrome", "content", fileName));
  }
}

function validatePackage() {
  // Reject legacy JSM markers that do not match the supported Zotero 9 target.
  const bootstrapPath = join(STAGE_DIR, "bootstrap.js");
  const bootstrapContent = readFileSync(bootstrapPath, "utf-8");

  if (bootstrapContent.includes("EXPORTED_SYMBOLS")) {
    throw new Error(
      "bootstrap.js contains EXPORTED_SYMBOLS, which is incompatible with the supported Zotero 9.x target. " +
      "Remove this legacy JSM marker."
    );
  }

  // Verify chrome registration is present for the supported Zotero 9 bootstrapped target.
  if (!bootstrapContent.includes("registerChrome") || !bootstrapContent.includes("amIAddonManagerStartup")) {
    throw new Error(
      "bootstrap.js is missing registerChrome call with amIAddonManagerStartup. " +
      "Supported Zotero 9 bootstrapped add-ons require dynamic chrome registration."
    );
  }

  // Verify manifest.json is valid JSON and has required Zotero fields
  const manifestPath = join(STAGE_DIR, "manifest.json");
  const manifest = JSON.parse(readFileSync(manifestPath, "utf-8"));

  // The supported Zotero 9 bootstrapped target uses Manifest V2.
  if (manifest.manifest_version !== 2) {
    throw new Error(
      `manifest.json has manifest_version ${manifest.manifest_version}, but Zotero bootstrapped plugins require Manifest V2.`
    );
  }

  // Zotero expects applications.zotero, not browser_specific_settings
  const zoteroSettings = manifest.applications?.zotero;

  if (!zoteroSettings) {
    throw new Error(
      "manifest.json is missing applications.zotero. Zotero bootstrapped plugins require this namespace."
    );
  }

  if (!zoteroSettings.id) {
    throw new Error(
      "manifest.json is missing id in applications.zotero"
    );
  }

  if (!zoteroSettings.strict_min_version) {
    throw new Error(
      "manifest.json is missing strict_min_version in applications.zotero"
    );
  }

  if (zoteroSettings.strict_min_version !== SUPPORTED_ZOTERO_MIN_VERSION) {
    throw new Error(
      `manifest.json strict_min_version must be ${SUPPORTED_ZOTERO_MIN_VERSION} for the supported Zotero target; ` +
      `received ${zoteroSettings.strict_min_version}.`
    );
  }

  if (!zoteroSettings.strict_max_version) {
    throw new Error(
      "manifest.json is missing strict_max_version in applications.zotero"
    );
  }

  if (zoteroSettings.strict_max_version !== SUPPORTED_ZOTERO_MAX_VERSION) {
    throw new Error(
      `manifest.json strict_max_version must be ${SUPPORTED_ZOTERO_MAX_VERSION} for the supported Zotero target; ` +
      `received ${zoteroSettings.strict_max_version}.`
    );
  }

  if (!zoteroSettings.update_url) {
    throw new Error(
      "manifest.json is missing update_url in applications.zotero. " +
      "Zotero requires this field even for local/dev installations."
    );
  }

  console.log("✓ Package validation passed");
  console.log(`  - Manifest V2 with Zotero ${zoteroSettings.strict_min_version} to ${zoteroSettings.strict_max_version}`);
  console.log(`  - ID: ${zoteroSettings.id}`);
  console.log("  - Chrome registration: present");
}

function addDirectory(zip, absoluteDirectory) {
  for (const entryName of readdirSync(absoluteDirectory)) {
    const entryPath = join(absoluteDirectory, entryName);
    const entryStats = statSync(entryPath);
    if (entryStats.isDirectory()) {
      addDirectory(zip, entryPath);
      continue;
    }

    const entryArchivePath = relative(STAGE_DIR, entryPath).replaceAll("\\", "/");
    zip.addFile(entryArchivePath, readFileSync(entryPath));
  }
}

async function bundle() {
  // Bundle bootstrap runtime with globalName so loadSubScript can find it
  await esbuild({
    bundle: true,
    define: {
      "process.env.NODE_ENV": '"production"',
      // Replace free `window` references with `globalThis` so React's event-system
      // callbacks don't throw ReferenceError when executed in Zotero's privileged
      // compartment context where `window` is not available as a lexical binding.
      "window": "globalThis",
    },
    entryPoints: {
      "chrome/content/bootstrap-runtime": join(ROOT, "src", "bootstrap-runtime.ts"),
    },
    format: "iife",
    globalName: "SciAgentBootstrapRuntime",
    minify: false,
    outdir: STAGE_DIR,
    platform: "browser",
    sourcemap: false,
    target: ["firefox115"],
  });

  // Bundle preferences pane without globalName
  await esbuild({
    bundle: true,
    define: {
      "process.env.NODE_ENV": '"production"',
    },
    entryPoints: {
      "chrome/content/preferences-pane": join(ROOT, "src", "preferences-pane.ts"),
    },
    format: "iife",
    minify: false,
    outdir: STAGE_DIR,
    platform: "browser",
    sourcemap: false,
    target: ["firefox115"],
  });

  // Bundle standalone main-window panel entry (loaded via loadSubScript into panel dialog)
  await esbuild({
    bundle: true,
    define: {
      "process.env.NODE_ENV": '"production"',
      // Replace free `window` references with `globalThis` so the bundle runs
      // correctly when loaded via loadSubScript into the panel chrome window.
      "window": "globalThis",
    },
    entryPoints: {
      "chrome/content/panel-entry": join(ROOT, "src", "panel-entry.ts"),
    },
    format: "iife",
    minify: false,
    outdir: STAGE_DIR,
    platform: "browser",
    sourcemap: false,
    target: ["firefox115"],
  });
}

async function buildAddon() {
  clean();
  mkdirSync(STAGE_DIR, { recursive: true });
  await bundle();
  copyStaticAssets();
  validatePackage();

  const zip = new AdmZip();
  addDirectory(zip, STAGE_DIR);
  zip.writeZip(XPI_PATH);

  console.log(`Staged add-on at ${STAGE_DIR}`);
  console.log(`Built XPI at ${XPI_PATH}`);
}

const command = process.argv[2] ?? "build";

if (command === "clean") {
  clean();
} else if (command === "build") {
  await buildAddon();
} else {
  throw new Error(`Unknown build command: ${command}`);
}
