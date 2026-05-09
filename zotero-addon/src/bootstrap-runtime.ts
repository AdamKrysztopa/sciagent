import { createRuntimeController } from "./host/runtime";
import "./ui/section.css";

// Export the runtime for esbuild IIFE with globalName.
// This ensures the bundled script assigns to the loadSubScript scope.
export default createRuntimeController();
