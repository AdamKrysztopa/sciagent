import { createRuntimeController } from "./host/runtime";
import "./ui/section.css";

const runtime = createRuntimeController();

declare global {
  interface Window {
    SciAgentBootstrapRuntime?: RuntimeController;
  }

  interface GlobalThis {
    SciAgentBootstrapRuntime?: RuntimeController;
  }
}

type RuntimeController = ReturnType<typeof createRuntimeController>;

const runtimeGlobal = globalThis as typeof globalThis & {
  SciAgentBootstrapRuntime?: RuntimeController;
};

runtimeGlobal.SciAgentBootstrapRuntime = runtime;
