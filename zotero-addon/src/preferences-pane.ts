import "./preferences-pane.css";

declare global {
  interface Window {
    SciAgentPreferencesPane?: {
      init(): void;
    };
  }
}

window.SciAgentPreferencesPane = {
  init(): void {},
};
