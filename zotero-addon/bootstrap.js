var EXPORTED_SYMBOLS = [];

var sciAgentRuntime = null;

function resolveRootURI(data) {
  if (data.rootURI) {
    return data.rootURI;
  }
  if (data.resourceURI?.spec) {
    return data.resourceURI.spec;
  }
  throw new Error("SciAgent bootstrap data did not contain a rootURI");
}

function getRuntime(data) {
  if (sciAgentRuntime !== null) {
    return sciAgentRuntime;
  }

  var runtimeScope = {};
  var rootURI = resolveRootURI(data);
  Services.scriptloader.loadSubScript(`${rootURI}chrome/content/bootstrap-runtime.js`, runtimeScope);
  sciAgentRuntime = runtimeScope.SciAgentBootstrapRuntime;
  if (!sciAgentRuntime) {
    throw new Error("SciAgent bootstrap runtime failed to initialize");
  }
  return sciAgentRuntime;
}

function install(data, reason) {
  getRuntime(data).install(data, reason);
}

function startup(data, reason) {
  getRuntime(data).startup(data, reason);
}

function shutdown(data, reason) {
  getRuntime(data).shutdown(data, reason);
}

function uninstall(data, reason) {
  getRuntime(data).uninstall(data, reason);
  sciAgentRuntime = null;
}

function onMainWindowLoad(data) {
  sciAgentRuntime?.onMainWindowLoad(data);
}

function onMainWindowUnload(data) {
  sciAgentRuntime?.onMainWindowUnload(data);
}
