import { describe, expect, it, vi } from "vitest";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { DEFAULT_ADDON_CONFIG } from "../../host/prefs";
import { detectLlmProvider, FirstRunConfigCard } from "./FirstRunConfigCard";

function renderCard(
  onSave = vi.fn(),
  onSkip = vi.fn(),
): string {
  return renderToStaticMarkup(
    createElement(FirstRunConfigCard, {
      config: { ...DEFAULT_ADDON_CONFIG },
      onSave,
      onSkip,
    }),
  );
}

describe("detectLlmProvider", () => {
  it("detects OpenAI from sk- prefix", () => {
    expect(detectLlmProvider("sk-abc123")).toBe("openai");
  });

  it("detects Anthropic from sk-ant- prefix (before OpenAI match)", () => {
    expect(detectLlmProvider("sk-ant-xyz")).toBe("anthropic");
  });

  it("detects xAI from xai- prefix", () => {
    expect(detectLlmProvider("xai-somekey")).toBe("xai");
  });

  it("detects Groq from gsk_ prefix", () => {
    expect(detectLlmProvider("gsk_mykey")).toBe("groq");
  });

  it("defaults to openai for unrecognised prefix", () => {
    expect(detectLlmProvider("unknown_key")).toBe("openai");
    expect(detectLlmProvider("")).toBe("openai");
  });
});

describe("FirstRunConfigCard rendering (P9.5)", () => {
  it("renders the Quick Setup heading", () => {
    expect(renderCard()).toContain("Quick Setup");
  });

  it("renders an LLM API Key input", () => {
    const html = renderCard();
    expect(html).toContain("LLM API Key");
    expect(html).toContain('type="password"');
  });

  it("renders a Zotero API Key input", () => {
    const html = renderCard();
    expect(html).toContain("Zotero API Key");
  });

  it("renders the zotero.org/settings/keys link", () => {
    const html = renderCard();
    expect(html).toContain("zotero.org/settings/keys");
  });

  it("renders Save & Continue and Skip buttons", () => {
    const html = renderCard();
    expect(html).toContain("Save");
    expect(html).toContain("Continue");
    expect(html).toContain("Skip");
  });

  it("Save button is disabled initially (no LLM key entered)", () => {
    const html = renderCard();
    // Button rendered disabled when canSave is false (initial state: llmKey = "")
    expect(html).toContain("disabled");
  });

  it("renders the Show advanced toggle button", () => {
    const html = renderCard();
    expect(html).toContain("Show advanced");
  });

  it("does not render the provider select by default (advanced hidden)", () => {
    const html = renderCard();
    expect(html).not.toContain("OpenAI");
    expect(html).not.toContain("Anthropic");
  });
});
