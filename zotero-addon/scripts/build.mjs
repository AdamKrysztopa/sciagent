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
  writeFileSync,
} from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const BUILD_DIR = join(ROOT, "build");
const STAGE_DIR = join(BUILD_DIR, "xpi");
const XPI_PATH = join(BUILD_DIR, "sciagent-zotero-addon.xpi");
const BUILD_UPDATE_RDF_PATH = join(BUILD_DIR, "update.rdf");
const SUPPORTED_ZOTERO_MIN_VERSION = "9.0.0";
const SUPPORTED_ZOTERO_MAX_VERSION = "9.*";
const DEFAULT_ZOTERO_UPDATE_URL = "https://raw.githubusercontent.com/AdamKrysztopa/sciagent/main/zotero-addon/update.rdf";
const ZOTERO_UPDATE_URL = process.env.SCIAGENT_ZOTERO_UPDATE_URL?.trim() || DEFAULT_ZOTERO_UPDATE_URL;

const STATIC_FILES = ["manifest.json", "update.rdf", "bootstrap.js", "prefs.js", "preferences.xhtml"];
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

function configureManifestForBuild() {
  const manifestPath = join(STAGE_DIR, "manifest.json");
  const manifest = JSON.parse(readFileSync(manifestPath, "utf-8"));
  const zoteroSettings = manifest.applications?.zotero;

  if (zoteroSettings === undefined) {
    writeFileSync(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`);
    return;
  }

  zoteroSettings.update_url = ZOTERO_UPDATE_URL;

  writeFileSync(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`);
}

function validateHttpUrl(value, fieldName) {
  let parsedUrl;
  try {
    parsedUrl = new URL(value);
  } catch {
    throw new Error(`${fieldName} must be a valid URL; received ${JSON.stringify(value)}.`);
  }

  if (parsedUrl.protocol !== "https:" && parsedUrl.protocol !== "http:") {
    throw new Error(`${fieldName} must use http:// or https://; received ${value}.`);
  }
}

function validateZoteroManifest(manifest) {
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

  if (typeof zoteroSettings.update_url !== "string" || zoteroSettings.update_url.trim().length === 0) {
    throw new Error(
      "manifest.json is missing applications.zotero.update_url. " +
      "Zotero requires this field even for local/dev installations."
    );
  }
  validateHttpUrl(zoteroSettings.update_url, "manifest.json applications.zotero.update_url");

  return zoteroSettings;
}

function validateUpdateRdfContent(updateRdfContent, manifest, zoteroSettings) {
  if (!updateRdfContent.includes(`urn:mozilla:extension:${zoteroSettings.id}`)) {
    throw new Error(`update.rdf must describe extension ${zoteroSettings.id}.`);
  }

  const expectedFields = [
    [`<em:version>${manifest.version}</em:version>`, "version"],
    [`<em:minVersion>${zoteroSettings.strict_min_version}</em:minVersion>`, "minimum Zotero version"],
    [`<em:maxVersion>${zoteroSettings.strict_max_version}</em:maxVersion>`, "maximum Zotero version"],
  ];

  for (const [expectedText, label] of expectedFields) {
    if (!updateRdfContent.includes(expectedText)) {
      throw new Error(`update.rdf is not aligned with manifest.json ${label}; missing ${expectedText}.`);
    }
  }

  const updateLinkMatch = updateRdfContent.match(/<em:updateLink>([^<]+)<\/em:updateLink>/);
  if (!updateLinkMatch) {
    throw new Error("update.rdf is missing em:updateLink for release update packages.");
  }

  validateHttpUrl(updateLinkMatch[1], "update.rdf em:updateLink");
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

  const panelHtmlPath = join(STAGE_DIR, "chrome", "content", "sciagent-panel.html");
  const panelHtmlContent = readFileSync(panelHtmlPath, "utf-8");
  if (!panelHtmlContent.includes("id=\"agt-panel-root\"") || !panelHtmlContent.includes("panel-entry.js")) {
    throw new Error(
      "sciagent-panel.html must include #agt-panel-root and load chrome://agt/content/panel-entry.js so the " +
      "main-window UI can boot without runtime script injection."
    );
  }

  // Verify manifest.json is valid JSON and has required Zotero fields
  const manifestPath = join(STAGE_DIR, "manifest.json");
  const manifest = JSON.parse(readFileSync(manifestPath, "utf-8"));
  const zoteroSettings = validateZoteroManifest(manifest);

  const updateRdfPath = join(STAGE_DIR, "update.rdf");
  const updateRdfContent = readFileSync(updateRdfPath, "utf-8");
  validateUpdateRdfContent(updateRdfContent, manifest, zoteroSettings);

  console.log("✓ Package validation passed");
  console.log(`  - Manifest V2 with Zotero ${zoteroSettings.strict_min_version} to ${zoteroSettings.strict_max_version}`);
  console.log(`  - ID: ${zoteroSettings.id}`);
  console.log(`  - Update URL: ${zoteroSettings.update_url}`);
  console.log("  - update.rdf: present and aligned");
  console.log("  - Chrome registration: present");
}

function validateBuiltXpi() {
  const zip = new AdmZip(XPI_PATH);
  const manifestEntry = zip.getEntry("manifest.json");
  if (manifestEntry === null) {
    throw new Error("Built XPI is missing manifest.json.");
  }

  const manifest = JSON.parse(zip.readAsText(manifestEntry));
  const zoteroSettings = validateZoteroManifest(manifest);

  const updateRdfEntry = zip.getEntry("update.rdf");
  if (updateRdfEntry === null) {
    throw new Error("Built XPI is missing update.rdf.");
  }

  validateUpdateRdfContent(zip.readAsText(updateRdfEntry), manifest, zoteroSettings);

  const panelEntry = zip.getEntry("chrome/content/panel-entry.js");
  if (panelEntry === null) {
    throw new Error("Built XPI is missing chrome/content/panel-entry.js.");
  }

  console.log("✓ Built XPI validation passed");
  console.log(`  - Packaged manifest update_url: ${zoteroSettings.update_url}`);
  console.log("  - Packaged update.rdf: present and aligned");
  console.log("  - Packaged panel-entry.js: present");
}

function exposeUpdateFeed() {
  copyFileSync(join(STAGE_DIR, "update.rdf"), BUILD_UPDATE_RDF_PATH);
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
  configureManifestForBuild();
  validatePackage();
  exposeUpdateFeed();

  const zip = new AdmZip();
  addDirectory(zip, STAGE_DIR);
  zip.writeZip(XPI_PATH);
  validateBuiltXpi();

  console.log(`Staged add-on at ${STAGE_DIR}`);
  console.log(`Exposed update feed at ${BUILD_UPDATE_RDF_PATH}`);
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
