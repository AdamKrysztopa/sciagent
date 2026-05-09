import type { AddonConfig } from "../../host/prefs";

type SaveState = "idle" | "saving" | "saved" | "error";

interface ConfigPanelProps {
  config: AddonConfig;
  onChange(field: keyof AddonConfig, value: boolean | string): void;
  onSave(): void;
  saveError: string | null;
  saveState: SaveState;
}

export function ConfigPanel({ config, onChange, onSave, saveError, saveState }: ConfigPanelProps) {
  return (
    <section className="agt-card">
      <div className="agt-section-heading">
        <h2>Preferences</h2>
        <button className="agt-button agt-button--ghost" disabled={saveState === "saving"} onClick={onSave} type="button">
          {saveState === "saving" ? "Saving..." : "Save Preferences"}
        </button>
      </div>
      <div className="agt-grid">
        <label className="agt-field">
          <span>Backend URL</span>
          <input
            className="agt-input"
            onChange={(event) => onChange("backendUrl", event.target.value)}
            type="url"
            value={config.backendUrl}
          />
        </label>
        <label className="agt-field">
          <span>Client ID</span>
          <input
            className="agt-input"
            onChange={(event) => onChange("clientId", event.target.value)}
            type="text"
            value={config.clientId}
          />
        </label>
      </div>
      <label className="agt-field">
        <span>API Key</span>
        <input
          className="agt-input"
          onChange={(event) => onChange("apiKey", event.target.value)}
          type="password"
          value={config.apiKey}
        />
      </label>
      <label className="agt-checkbox-row">
        <input
          checked={config.enablePdfImports}
          onChange={(event) => onChange("enablePdfImports", event.target.checked)}
          type="checkbox"
        />
        <span>Store PDF import preference placeholder</span>
      </label>
      <p className="agt-small-note">
        The toggle is persisted now for future ZAP-8 work, but the MVP keeps all writes on the backend through <code>/resume</code>.
      </p>
      {saveState === "saved" ? <span className="agt-pill agt-pill--ok">Preferences saved</span> : null}
      {saveError !== null ? <div className="agt-error">{saveError}</div> : null}
    </section>
  );
}
