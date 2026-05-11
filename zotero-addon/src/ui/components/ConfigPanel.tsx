import type { AddonConfig } from "../../host/prefs";

type SaveState = "idle" | "saving" | "saved" | "error";

interface ConfigPanelProps {
  config: AddonConfig;
  onChange(field: keyof AddonConfig, value: boolean | number | null | string): void;
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

      <h3 className="agt-subsection-heading">Connection &amp; Auth</h3>
      <p className="agt-small-note">
        Provider and source API keys are backend-owned. Configure them in the backend <code>.env</code> file, not here.
      </p>
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

      <h3 className="agt-subsection-heading">Search Defaults</h3>
      <p className="agt-small-note">
        These defaults pre-fill the pre-search filter composer. They are sent with every initial search request.
      </p>
      <label className="agt-field">
        <span>Default Collection</span>
        <input
          className="agt-input"
          onChange={(event) => onChange("defaultCollection", event.target.value)}
          placeholder="Inbox"
          type="text"
          value={config.defaultCollection}
        />
      </label>
      <div className="agt-grid--compact">
        <label className="agt-field">
          <span>Min Year</span>
          <input
            className="agt-number"
            max={2100}
            min={1900}
            onChange={(event) => {
              onChange("defaultMinYear", event.target.value === "" ? null : Number(event.target.value));
            }}
            type="number"
            value={config.defaultMinYear ?? ""}
          />
        </label>
        <label className="agt-field">
          <span>Max Year</span>
          <input
            className="agt-number"
            max={2100}
            min={1900}
            onChange={(event) => {
              onChange("defaultMaxYear", event.target.value === "" ? null : Number(event.target.value));
            }}
            type="number"
            value={config.defaultMaxYear ?? ""}
          />
        </label>
        <label className="agt-field">
          <span>Min Citations</span>
          <input
            className="agt-number"
            min={0}
            onChange={(event) => {
              const n = Number(event.target.value);
              onChange("defaultMinCitations", Number.isNaN(n) ? 0 : n);
            }}
            type="number"
            value={config.defaultMinCitations}
          />
        </label>
      </div>
      <label className="agt-checkbox-row">
        <input
          checked={config.defaultOpenAccessOnly}
          onChange={(event) => onChange("defaultOpenAccessOnly", event.target.checked)}
          type="checkbox"
        />
        <span>Open access papers only by default</span>
      </label>
      <label className="agt-checkbox-row">
        <input
          checked={config.spellCheckEnabled}
          onChange={(event) => onChange("spellCheckEnabled", event.target.checked)}
          type="checkbox"
        />
        <span>Spell-check queries before search</span>
      </label>

      <h3 className="agt-subsection-heading">PDF Imports</h3>
      <label className="agt-checkbox-row">
        <input
          checked={config.enablePdfImports}
          onChange={(event) => onChange("enablePdfImports", event.target.checked)}
          type="checkbox"
        />
        <span>Enable PDF import after write</span>
      </label>
      <p className="agt-small-note">
        The MVP saves this toggle, but all writes still stay on the backend through <code>/resume</code>.
      </p>
      {saveState === "saved" ? <span className="agt-pill agt-pill--ok">Preferences saved</span> : null}
      {saveError !== null ? <div className="agt-error">{saveError}</div> : null}
    </section>
  );
}
