/**
 * SciAgent bootstrap for Zotero 7+
 * Based on Zotero plugin template and Make It Red example
 */

var sciAgentRuntime = null;
var chromeHandle = null;
var l10nRegistrySource = null;

function resolveRootURI(data) {
  if (data.rootURI) {
    return data.rootURI;
  }
  if (data.resourceURI?.spec) {
    return data.resourceURI.spec;
  }
  throw new Error("SciAgent bootstrap data did not contain a rootURI");
}

// Load L10nRegistry for Zotero 7+
// Returns null if unavailable; caller must handle gracefully
function loadL10nRegistry() {
  try {
    return ChromeUtils.importESModule("resource://gre/modules/L10nRegistry.sys.mjs");
  } catch (e) {
    Zotero.debug(`[SciAgent] WARNING: L10nRegistry.sys.mjs not available: ${e}`);
    Zotero.debug("[SciAgent] Fluent localization will not be available; using fallback labels");
    return null;
  }
}

// Load the compiled runtime bundle lazily — only called from startup().
// Do NOT call this from install() or uninstall(): the Zotero global and
// document context are not available at those lifecycle points, and loading
// the React bundle at that time causes the XPI install to fail.
function loadRuntime(data) {
  if (sciAgentRuntime !== null) {
    Zotero.debug("[SciAgent] Runtime already loaded, reusing instance");
    return sciAgentRuntime;
  }

  var runtimeScope;
  var rootURI;
  var scriptPath;
  try {
    runtimeScope = {};
    rootURI = resolveRootURI(data);
    scriptPath = `${rootURI}chrome/content/bootstrap-runtime.js`;
    Zotero.debug(`[SciAgent] Loading runtime script: ${scriptPath}`);
    Services.scriptloader.loadSubScript(scriptPath, runtimeScope);
    // esbuild IIFE with default export returns { default: runtime }
    sciAgentRuntime = runtimeScope.SciAgentBootstrapRuntime?.default ?? runtimeScope.SciAgentBootstrapRuntime;
    if (!sciAgentRuntime) {
      throw new Error("SciAgent bootstrap runtime failed to initialize - SciAgentBootstrapRuntime not found in scope");
    }
    Zotero.debug("[SciAgent] Runtime instance created successfully");
    return sciAgentRuntime;
  } catch (error) {
    Zotero.debug(`[SciAgent] Failed to load runtime: ${error}`);
    Zotero.logError(error);
    throw error;
  }
}

// install() must remain a no-op. Zotero calls this before the Zotero global
// and browser document are available. Loading the bundle here crashes the install.
function install(_data, _reason) {}

function startup(data, reason) {
  var aomStartup;
  var rootURI;
  var manifestURI;
  var runtime;
  try {
    Zotero.debug("[SciAgent] Bootstrap startup initiated");
    // Register chrome paths dynamically for Zotero 7+
    aomStartup = Components.classes[
      "@mozilla.org/addons/addon-manager-startup;1"
    ].getService(Components.interfaces.amIAddonManagerStartup);
    rootURI = resolveRootURI(data);
    Zotero.debug(`[SciAgent] Resolved root URI: ${rootURI}`);

    manifestURI = Services.io.newURI(`${rootURI}manifest.json`);
    chromeHandle = aomStartup.registerChrome(manifestURI, [
      ["content", "agt", `${rootURI}chrome/content/`],
      ["locale", "agt", "en-US", `${rootURI}locale/en-US/`],
      ["locale", "agt", "en-GB", `${rootURI}locale/en-US/`],
      ["locale", "agt", "pl-PL", `${rootURI}locale/en-US/`],
    ]);
    Zotero.debug("[SciAgent] Chrome paths registered (en-US, en-GB, pl-PL fallback)");

    // Register Fluent localization source for data-l10n-id resolution
    // This is optional; if it fails, UI will use fallback labels
    try {
      const L10nResult = loadL10nRegistry();
      if (L10nResult !== null) {
        const { L10nRegistry, FileSource } = L10nResult;
        l10nRegistrySource = new FileSource(
          "agt",
          ["en-US"],
          `${rootURI}locale/{locale}/`
        );
        L10nRegistry.getInstance().registerSources([l10nRegistrySource]);
        Zotero.debug("[SciAgent] Fluent localization source registered (agt)");
      }
    } catch (error) {
      Zotero.debug(`[SciAgent] WARNING: Failed to register Fluent source: ${error}`);
      Zotero.debug("[SciAgent] Continuing startup with fallback labels");
      l10nRegistrySource = null;
    }

    Zotero.debug("[SciAgent] Loading runtime bundle...");
    runtime = loadRuntime(data);
    Zotero.debug("[SciAgent] Runtime bundle loaded, calling startup");
    runtime.startup(data, reason);
    Zotero.debug("[SciAgent] Bootstrap startup complete");
  } catch (error) {
    Zotero.debug(`[SciAgent] FATAL: Bootstrap startup failed: ${error}`);
    Zotero.logError(error);
    throw error;
  }
}

function shutdown(data, reason) {
  try {
    Zotero.debug(`[SciAgent] Bootstrap shutdown initiated (reason: ${reason})`);
    if (reason === APP_SHUTDOWN) {
      Zotero.debug("[SciAgent] App shutdown - skipping cleanup");
      return;
    }

    if (sciAgentRuntime !== null) {
      Zotero.debug("[SciAgent] Calling runtime shutdown");
      sciAgentRuntime.shutdown(data, reason);
    }

    if (l10nRegistrySource !== null) {
      try {
        const L10nResult = loadL10nRegistry();
        if (L10nResult !== null) {
          const { L10nRegistry } = L10nResult;
          L10nRegistry.getInstance().removeSources(["agt"]);
          Zotero.debug("[SciAgent] Fluent localization source unregistered");
        }
        l10nRegistrySource = null;
      } catch (error) {
        Zotero.debug(`[SciAgent] Failed to unregister L10n source: ${error}`);
        Zotero.logError(error);
      }
    }

    if (chromeHandle) {
      Zotero.debug("[SciAgent] Destructing chrome handle");
      chromeHandle.destruct();
      chromeHandle = null;
    }
    Zotero.debug("[SciAgent] Bootstrap shutdown complete");
  } catch (error) {
    Zotero.debug(`[SciAgent] Error during shutdown: ${error}`);
    Zotero.logError(error);
  }
}

function uninstall(data, reason) {
  if (sciAgentRuntime !== null) {
    sciAgentRuntime.uninstall(data, reason);
    sciAgentRuntime = null;
  }
}

function onMainWindowLoad(data) {
  sciAgentRuntime?.onMainWindowLoad(data);
}

function onMainWindowUnload(data) {
  sciAgentRuntime?.onMainWindowUnload(data);
}
