import { useState } from "react";

import type { AddonConfig } from "../../host/prefs";
import { CustomSelect } from "./CustomSelect";

const PROVIDER_OPTIONS = [
  { label: "OpenAI", value: "openai" },
  { label: "Anthropic", value: "anthropic" },
  { label: "xAI (Grok)", value: "xai" },
  { label: "Groq", value: "groq" },
] as const;

const LIBRARY_TYPE_OPTIONS = [
  { value: "user", label: "User library" },
  { value: "group", label: "Group library" },
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
  const isRemote = config.backendMode === "remote";

  const [llmKey, setLlmKey] = useState("");
  const [provider, setProvider] = useState(config.llmProvider || "openai");
  const [zoteroApiKey, setZoteroApiKey] = useState(config.zoteroApiKey);
  const [zoteroLibraryId, setZoteroLibraryId] = useState(config.zoteroLibraryId);
  const [zoteroLibraryType, setZoteroLibraryType] = useState<"user" | "group">(config.zoteroLibraryType);
  const [showAdvanced, setShowAdvanced] = useState(false);

  function handleLlmKeyChange(value: string) {
    setLlmKey(value);
    if (value.trim().length > 0) {
      setProvider(detectLlmProvider(value.trim()));
    }
  }

  function handleSave() {
    const update: Partial<AddonConfig> = {
      zoteroApiKey: zoteroApiKey.trim(),
      zoteroLibraryId: zoteroLibraryId.trim(),
      zoteroLibraryType,
    };
    if (!isRemote) {
      update.llmProvider = provider;
      if (provider === "openai") update.openaiApiKey = llmKey.trim();
      else if (provider === "anthropic") update.anthropicApiKey = llmKey.trim();
      else if (provider === "xai") update.xaiApiKey = llmKey.trim();
      else if (provider === "groq") update.groqApiKey = llmKey.trim();
    }
    onSave(update);
  }

  const canSave = isRemote
    ? zoteroApiKey.trim().length > 0 && zoteroLibraryId.trim().length > 0
    : llmKey.trim().length > 0;

  return (
    <div className="agt-state-view">
      <section className="agt-card" aria-labelledby="agt-frcc-heading">
        <div className="agt-section-heading">
          <h2 id="agt-frcc-heading">Quick Setup</h2>
        </div>

        {isRemote ? (
          <>
            <p className="agt-small-note">
              Enter your Zotero credentials so the remote backend can write to your library.
              Your credentials are sent per-request and never stored server-side.
            </p>

            <label className="agt-field">
              <span>Zotero API Key</span>
              <input
                autoComplete="off"
                className="agt-input"
                onChange={(e) => { setZoteroApiKey(e.target.value); }}
                placeholder="your Zotero Web API key"
                type="password"
                value={zoteroApiKey}
              />
            </label>
            <label className="agt-field">
              <span>Library ID</span>
              <input
                autoComplete="off"
                className="agt-input"
                onChange={(e) => { setZoteroLibraryId(e.target.value); }}
                placeholder="e.g. 1234567"
                type="text"
                value={zoteroLibraryId}
              />
            </label>
            <div className="agt-field">
              <span>Library Type</span>
              <CustomSelect
                onChange={(v) => { setZoteroLibraryType(v as "user" | "group"); }}
                options={[...LIBRARY_TYPE_OPTIONS]}
                value={zoteroLibraryType}
              />
            </div>
            <p className="agt-small-note">
              <a href="https://www.zotero.org/settings/keys" rel="noreferrer" target="_blank">
                Get your API key and library ID on zotero.org
              </a>
            </p>
          </>
        ) : (
          <>
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
              <a href="https://www.zotero.org/settings/keys" rel="noreferrer" target="_blank">
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
                <div className="agt-field">
                  <span>LLM Provider</span>
                  <CustomSelect
                    onChange={setProvider}
                    options={[...PROVIDER_OPTIONS]}
                    value={provider}
                  />
                </div>
              </div>
            ) : null}
          </>
        )}

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
