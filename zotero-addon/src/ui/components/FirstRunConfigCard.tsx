import { useState } from "react";

import type { AddonConfig } from "../../host/prefs";

const PROVIDER_OPTIONS = [
  { label: "OpenAI", value: "openai" },
  { label: "Anthropic", value: "anthropic" },
  { label: "xAI (Grok)", value: "xai" },
  { label: "Groq", value: "groq" },
] as const;

export function detectLlmProvider(key: string): string {
  if (key.startsWith("sk-ant-")) return "anthropic";
  if (key.startsWith("xai-")) return "xai";
  if (key.startsWith("gsk_")) return "groq";
  if (key.startsWith("sk-")) return "openai";
  return "openai";
}

interface FirstRunConfigCardProps {
  config: AddonConfig;
  onSave(update: Partial<AddonConfig>): void;
  onSkip(): void;
}

export function FirstRunConfigCard({ config, onSave, onSkip }: FirstRunConfigCardProps) {
  const [llmKey, setLlmKey] = useState("");
  const [zoteroApiKey, setZoteroApiKey] = useState(config.apiKey);
  const [provider, setProvider] = useState(config.llmProvider || "openai");
  const [showAdvanced, setShowAdvanced] = useState(false);

  function handleLlmKeyChange(value: string) {
    setLlmKey(value);
    if (value.trim().length > 0) {
      setProvider(detectLlmProvider(value.trim()));
    }
  }

  function handleSave() {
    const update: Partial<AddonConfig> = {
      llmProvider: provider,
      apiKey: zoteroApiKey.trim(),
    };
    if (provider === "openai") update.openaiApiKey = llmKey.trim();
    else if (provider === "anthropic") update.anthropicApiKey = llmKey.trim();
    else if (provider === "xai") update.xaiApiKey = llmKey.trim();
    else if (provider === "groq") update.groqApiKey = llmKey.trim();
    onSave(update);
  }

  const canSave = llmKey.trim().length > 0;

  return (
    <div className="agt-state-view">
      <section className="agt-card" aria-labelledby="agt-frcc-heading">
        <div className="agt-section-heading">
          <h2 id="agt-frcc-heading">Quick Setup</h2>
        </div>
        <p className="agt-small-note">
          Enter one LLM API key to start searching. Zotero credentials are only needed
          for cloud sync — skip them if you are using local Zotero storage.
        </p>

        <label className="agt-field">
          <span>LLM API Key</span>
          <input
            autoComplete="off"
            className="agt-input"
            onChange={(e) => { handleLlmKeyChange(e.target.value); }}
            placeholder="sk-… / sk-ant-… / xai-… / gsk_…"
            type="password"
            value={llmKey}
          />
          {llmKey.trim().length > 0 ? (
            <span className="agt-small-note agt-meta">
              Detected provider: <strong>{provider}</strong>
            </span>
          ) : null}
        </label>

        <label className="agt-field">
          <span>Zotero API Key <span className="agt-meta">(optional)</span></span>
          <input
            autoComplete="off"
            className="agt-input"
            onChange={(e) => { setZoteroApiKey(e.target.value); }}
            placeholder="your Zotero Web API key"
            type="password"
            value={zoteroApiKey}
          />
        </label>
        <p className="agt-small-note">
          <a
            href="https://www.zotero.org/settings/keys"
            rel="noreferrer"
            target="_blank"
          >
            Find these on zotero.org/settings/keys
          </a>
        </p>

        <button
          className="agt-button agt-button--ghost agt-button--sm"
          onClick={() => { setShowAdvanced(!showAdvanced); }}
          type="button"
        >
          {showAdvanced ? "Hide advanced" : "Show advanced"}
        </button>

        {showAdvanced ? (
          <div className="agt-advanced-section">
            <label className="agt-field">
              <span>LLM Provider</span>
              <select
                className="agt-input"
                onChange={(e) => { setProvider(e.target.value); }}
                value={provider}
              >
                {PROVIDER_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
            </label>
          </div>
        ) : null}

        <div className="agt-action-cluster">
          <button
            className="agt-button agt-button--warn"
            disabled={!canSave}
            onClick={handleSave}
            type="button"
          >
            Save &amp; Continue
          </button>
          <button
            className="agt-button agt-button--ghost"
            onClick={onSkip}
            type="button"
          >
            Skip
          </button>
        </div>
      </section>
    </div>
  );
}
