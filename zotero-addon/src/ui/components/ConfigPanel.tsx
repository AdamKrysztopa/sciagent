import { useState } from "react";

import type { KeyValidateResponse, PreflightStatus } from "../../shared/contracts";
import { VALIDATABLE_PROVIDERS } from "../../shared/contracts";
import type { AddonConfig } from "../../host/prefs";
import { CustomSelect } from "./CustomSelect";

const LIBRARY_TYPE_OPTIONS = [
  { value: "user", label: "User library" },
  { value: "group", label: "Group library" },
] as const;

const LLM_PROVIDER_OPTIONS = [
  { value: "openai", label: "OpenAI" },
  { value: "anthropic", label: "Anthropic" },
  { value: "deepseek", label: "DeepSeek" },
  { value: "xai", label: "xAI (Grok)" },
  { value: "groq", label: "Groq" },
  { value: "openai-compatible", label: "OpenAI-compatible" },
] as const;

type SaveState = "idle" | "saving" | "saved" | "error";
type ValidationState = "idle" | "validating" | "valid" | "invalid";

interface ProviderKeyRowProps {
  provider: string;
  onValidate(provider: string, apiKey: string): Promise<KeyValidateResponse>;
}

function ProviderKeyRow({ provider, onValidate }: ProviderKeyRowProps) {
  const [apiKey, setApiKey] = useState("");
  const [validationState, setValidationState] = useState<ValidationState>("idle");
  const [validationError, setValidationError] = useState<string | null>(null);

  const handleValidate = async () => {
    if (!apiKey.trim()) return;
    setValidationState("validating");
    setValidationError(null);
    try {
      const result = await onValidate(provider, apiKey.trim());
      if (result.valid) {
        setValidationState("valid");
      } else {
        setValidationState("invalid");
        setValidationError(result.error ?? "validation_failed");
      }
    } catch {
      setValidationState("invalid");
      setValidationError("network_error");
    }
  };

  return (
    <div className="agt-provider-key-row">
      <label className="agt-field">
        <span>{provider}</span>
        <div className="agt-key-input-row">
          <input
            className="agt-input"
            disabled={validationState === "validating"}
            onChange={(event) => { setApiKey(event.target.value); setValidationState("idle"); }}
            placeholder={`${provider} API key`}
            type="password"
            value={apiKey}
          />
          <button
            className="agt-button agt-button--ghost"
            disabled={!apiKey.trim() || validationState === "validating"}
            onClick={() => { void handleValidate(); }}
            type="button"
          >
            {validationState === "validating" ? "\u2026" : "Validate"}
          </button>
        </div>
      </label>
      {validationState === "valid" ? (
        <output className="agt-validation-ok">✓ Key is valid</output>
      ) : validationState === "invalid" ? (
        <p className="agt-validation-error" role="alert">✗ {validationError ?? "Invalid key"}</p>
      ) : null}
    </div>
  );
}

type ZoteroTestState = "idle" | "testing" | "ok" | "error";

interface ConfigPanelProps {
  addonVersion?: string;
  config: AddonConfig;
  onChange(field: keyof AddonConfig, value: boolean | number | null | string): void;
  onSave(): void;
  saveError: string | null;
  saveState: SaveState;
  onValidateKey(provider: string, apiKey: string): Promise<KeyValidateResponse>;
  onTestZotero(): Promise<PreflightStatus>;
}

export function ConfigPanel({ addonVersion, config, onChange, onSave, saveError, saveState, onValidateKey, onTestZotero }: ConfigPanelProps) {
  const [zoteroTestState, setZoteroTestState] = useState<ZoteroTestState>("idle");
  const [zoteroTestMessage, setZoteroTestMessage] = useState<string | null>(null);

  const handleTestZotero = async () => {
    setZoteroTestState("testing");
    setZoteroTestMessage(null);
    try {
      const result = await onTestZotero();
      if (result.ok) {
        const name = result.library_name ?? "Library";
        setZoteroTestState("ok");
        setZoteroTestMessage(`${name} verified`);
      } else {
        setZoteroTestState("error");
        setZoteroTestMessage(result.message ?? "Preflight failed");
      }
    } catch (err) {
      setZoteroTestState("error");
      setZoteroTestMessage(err instanceof Error ? err.message : "Connection failed");
    }
  };

  const canTestZotero = config.zoteroApiKey.length > 0 && config.zoteroLibraryId.length > 0;
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
      <div className="agt-field">
        <span>Backend Mode</span>
        <CustomSelect
          onChange={(v) => onChange("backendMode", v)}
          options={[
            { value: "remote", label: "Remote (hosted backend)" },
            { value: "local", label: "Local (embedded server)" },
          ]}
          value={config.backendMode}
        />
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

      <h3 className="agt-subsection-heading">Zotero Account</h3>
      <p className="agt-small-note">
        Required when using a remote backend. The backend writes to your Zotero library using these
        credentials — they are never stored server-side.
      </p>
      <label className="agt-field">
        <span>Zotero API Key</span>
        <input
          className="agt-input"
          onChange={(event) => onChange("zoteroApiKey", event.target.value)}
          placeholder="your Zotero Web API key"
          type="password"
          value={config.zoteroApiKey}
        />
      </label>
      <label className="agt-field">
        <span>Library ID</span>
        <input
          className="agt-input"
          onChange={(event) => onChange("zoteroLibraryId", event.target.value)}
          placeholder="e.g. 1234567"
          type="text"
          value={config.zoteroLibraryId}
        />
      </label>
      <div className="agt-field">
        <span>Library Type</span>
        <CustomSelect
          onChange={(v) => onChange("zoteroLibraryType", v)}
          options={[...LIBRARY_TYPE_OPTIONS]}
          value={config.zoteroLibraryType}
        />
      </div>
      <p className="agt-small-note">
        <a href="https://www.zotero.org/settings/keys" rel="noreferrer" target="_blank">
          Get your API key and library ID on zotero.org
        </a>
      </p>
      <div className="agt-test-connection-row">
        <button
          className="agt-button agt-button--ghost"
          disabled={!canTestZotero || zoteroTestState === "testing"}
          onClick={() => { void handleTestZotero(); }}
          type="button"
        >
          {zoteroTestState === "testing" ? "… Testing" : "Test Zotero Connection"}
        </button>
        {zoteroTestState === "ok" && zoteroTestMessage !== null ? (
          <output className="agt-validation-ok">{"✓"} {zoteroTestMessage}</output>
        ) : null}
        {zoteroTestState === "error" && zoteroTestMessage !== null ? (
          <p className="agt-validation-error" role="alert">{"✗"} {zoteroTestMessage}</p>
        ) : null}
      </div>

      <h3 className="agt-subsection-heading">LLM Provider</h3>
      <p className="agt-small-note">
        Select the LLM provider to use for query rewriting and summarization.
        Keys are stored in Zotero preferences and passed securely to the backend.
      </p>
      <div className="agt-field">
        <span>Provider</span>
        <CustomSelect
          onChange={(v) => onChange("llmProvider", v)}
          options={[
            { value: "openai", label: "OpenAI" },
            { value: "anthropic", label: "Anthropic" },
            { value: "xai", label: "xAI (Grok)" },
            { value: "groq", label: "Groq" },
            { value: "ollama", label: "Ollama (local, no key)" },
            { value: "custom", label: "Custom OpenAI-compatible" },
          ]}
          value={config.llmProvider}
        />
      </div>
      {config.llmProvider === "openai" && (
        <label className="agt-field">
          <span>OpenAI API Key</span>
          <input
            className="agt-input"
            onChange={(event) => onChange("openaiApiKey", event.target.value)}
            placeholder="sk-..."
            type="password"
            value={config.openaiApiKey}
          />
        </label>
      )}
      {config.llmProvider === "anthropic" && (
        <label className="agt-field">
          <span>Anthropic API Key</span>
          <input
            className="agt-input"
            onChange={(event) => onChange("anthropicApiKey", event.target.value)}
            placeholder="sk-ant-..."
            type="password"
            value={config.anthropicApiKey}
          />
        </label>
      )}
      {config.llmProvider === "xai" && (
        <label className="agt-field">
          <span>xAI API Key</span>
          <input
            className="agt-input"
            onChange={(event) => onChange("xaiApiKey", event.target.value)}
            placeholder="xai-..."
            type="password"
            value={config.xaiApiKey}
          />
        </label>
      )}
      {config.llmProvider === "groq" && (
        <label className="agt-field">
          <span>Groq API Key</span>
          <input
            className="agt-input"
            onChange={(event) => onChange("groqApiKey", event.target.value)}
            placeholder="gsk_..."
            type="password"
            value={config.groqApiKey}
          />
        </label>
      )}
      {config.llmProvider === "ollama" && (
        <p className="agt-small-note">
          No API key required. Ollama must be running at localhost:11434 (or set a custom base URL
          below).
        </p>
      )}
      {(config.llmProvider === "ollama" || config.llmProvider === "custom") && (
        <label className="agt-field">
          <span>Base URL</span>
          <input
            className="agt-input"
            onChange={(event) => onChange("llmBaseUrl", event.target.value)}
            placeholder={
              config.llmProvider === "ollama"
                ? "http://localhost:11434/v1"
                : "https://api.deepseek.com/v1"
            }
            type="url"
            value={config.llmBaseUrl}
          />
        </label>
      )}
      <label className="agt-field">
        <span>Model Name</span>
        <input
          className="agt-input"
          onChange={(event) => onChange("llmModel", event.target.value)}
          placeholder={
            config.llmProvider === "openai" ? "gpt-5.4" :
            config.llmProvider === "anthropic" ? "claude-opus-4-6" :
            config.llmProvider === "xai" ? "grok-4" :
            config.llmProvider === "groq" ? "llama-3.3-70b-versatile" :
            config.llmProvider === "ollama" ? "llama3.2" :
            "deepseek-chat"
          }
          type="text"
          value={config.llmModel}
        />
      </label>
      <p className="agt-small-note">Leave blank to use the provider default.</p>

      <h3 className="agt-subsection-heading">LLM Override (Remote Mode)</h3>
      <p className="agt-small-note">
        The remote backend uses its own LLM key by default. Enable this to use your own key instead
        (charged to your account, not the operator&apos;s).
      </p>
      <label className="agt-checkbox-row">
        <input
          checked={config.useCustomLlm}
          onChange={(event) => onChange("useCustomLlm", event.target.checked)}
          type="checkbox"
        />
        <span>Use my own LLM key for remote backend</span>
      </label>
      {config.useCustomLlm ? (
        <>
          <div className="agt-field">
            <span>LLM Provider</span>
            <CustomSelect
              onChange={(v) => onChange("customLlmProvider", v)}
              options={[...LLM_PROVIDER_OPTIONS]}
              value={config.customLlmProvider || "openai"}
            />
          </div>
          <label className="agt-field">
            <span>API Key</span>
            <input
              className="agt-input"
              onChange={(event) => onChange("customLlmApiKey", event.target.value)}
              placeholder="your LLM provider key"
              type="password"
              value={config.customLlmApiKey}
            />
          </label>
          <label className="agt-field">
            <span>Base URL <span className="agt-meta">(optional)</span></span>
            <input
              className="agt-input"
              onChange={(event) => onChange("customLlmBaseUrl", event.target.value)}
              placeholder="https://api.openai.com/v1"
              type="url"
              value={config.customLlmBaseUrl}
            />
          </label>
          <label className="agt-field">
            <span>Model <span className="agt-meta">(optional)</span></span>
            <input
              className="agt-input"
              onChange={(event) => onChange("customLlmModel", event.target.value)}
              placeholder="leave blank for provider default"
              type="text"
              value={config.customLlmModel}
            />
          </label>
        </>
      ) : null}

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

      <h3 className="agt-subsection-heading">Write Path</h3>
      <label className="agt-checkbox-row">
        <input
          checked={config.nativeWriteEnabled}
          onChange={(event) => onChange("nativeWriteEnabled", event.target.checked)}
          type="checkbox"
        />
        <span>Use native Zotero write (ZAP path)</span>
      </label>
      <p className="agt-small-note">
        When enabled, approved items are written directly via the Zotero JS API instead of the backend pyzotero path. Faster and works offline once results are loaded.
      </p>
      <label className="agt-checkbox-row">
        <input
          checked={config.enablePdfImports}
          onChange={(event) => onChange("enablePdfImports", event.target.checked)}
          type="checkbox"
        />
        <span>Enable PDF import after write</span>
      </label>
      {saveState === "saved" ? <span className="agt-pill agt-pill--ok">Preferences saved</span> : null}
      {saveError !== null ? <div className="agt-error">{saveError}</div> : null}

      <h3 className="agt-subsection-heading">Validate Server-Side API Keys</h3>
      <p className="agt-small-note">
        These buttons check whether your backend already has a key configured for each optional
        provider. Keys must be set in the backend <code>.env</code> file
        (e.g. <code>AGT_SEMANTIC_SCHOLAR_API_KEY</code>) — entering a key here
        does <strong>not</strong> store it. Note: providers without a key still work at free-tier
        rate limits (Semantic Scholar is always reachable without a key).
      </p>
      <div className="agt-provider-key-grid">
        {VALIDATABLE_PROVIDERS.map((provider) => (
          <ProviderKeyRow
            key={provider}
            provider={provider}
            onValidate={onValidateKey}
          />
        ))}
      </div>

      {addonVersion !== undefined ? (
        <p className="agt-version-footer">SciAgent v{addonVersion}</p>
      ) : null}
    </section>
  );
}
