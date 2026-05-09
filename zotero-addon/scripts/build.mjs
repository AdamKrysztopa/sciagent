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

const STATIC_FILES = ["manifest.json", "bootstrap.js", "prefs.js", "preferences.xhtml"];
const STATIC_DIRS = ["icons", "locale"];

const ENTRY_POINTS = {
  "chrome/content/bootstrap-runtime": join(ROOT, "src", "bootstrap-runtime.ts"),
  "chrome/content/preferences-pane": join(ROOT, "src", "preferences-pane.ts"),
};

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
  await esbuild({
    bundle: true,
    define: {
      "process.env.NODE_ENV": '"production"',
    },
    entryPoints: ENTRY_POINTS,
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
