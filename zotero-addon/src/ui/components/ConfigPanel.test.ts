import { describe, expect, it, vi } from "vitest";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { DEFAULT_ADDON_CONFIG } from "../../host/prefs";
import type { KeyValidateResponse } from "../../shared/contracts";
import { VALIDATABLE_PROVIDERS } from "../../shared/contracts";
import { ConfigPanel } from "./ConfigPanel";

function renderPanel(
  onValidateKey?: (provider: string, apiKey: string) => Promise<KeyValidateResponse>,
  addonVersion?: string,
): string {
  return renderToStaticMarkup(
    createElement(ConfigPanel, {
      addonVersion,
      config: { ...DEFAULT_ADDON_CONFIG },
      onChange: () => {},
      onSave: () => {},
      saveError: null,
      saveState: "idle" as const,
      onValidateKey:
        onValidateKey ??
        vi.fn().mockResolvedValue({ provider: "x", valid: true, error: null }),
      onTestZotero: vi.fn().mockResolvedValue({ ok: true, library_name: "Test Library" }),
    }),
  );
}

describe("ConfigPanel version footer (P9.3)", () => {
  it("shows version string when addonVersion is provided", () => {
    const html = renderPanel(undefined, "0.2.0");
    expect(html).toContain("SciAgent v0.2.0");
    expect(html).toContain("agt-version-footer");
  });

  it("omits version footer when addonVersion is not provided", () => {
    const html = renderPanel();
    expect(html).not.toContain("agt-version-footer");
  });
});

describe("ConfigPanel Provider API Keys section (P8.10-B)", () => {
  it("renders the Provider API Keys section heading", () => {
    const html = renderPanel();
    expect(html).toContain("Validate Server-Side API Keys");
  });

  it("renders a row for every VALIDATABLE_PROVIDER", () => {
    const html = renderPanel();
    for (const provider of VALIDATABLE_PROVIDERS) {
      expect(html).toContain(provider);
    }
  });

  it("renders the backend .env note about key storage location", () => {
    const html = renderPanel();
    expect(html).toContain(".env");
    expect(html).toContain("store it");
  });

  it("renders a Validate button for each provider", () => {
    const html = renderPanel();
    // The description text also contains "Validate", so total matches = providers + 1
    const validateMatches = html.match(/Validate/g) ?? [];
    expect(validateMatches.length).toBeGreaterThanOrEqual(VALIDATABLE_PROVIDERS.length);
    // Confirm each button appears: match type="button" elements containing Validate
    expect(html.match(/type="button"[^>]*>[^<]*Validate[^<]*<\/button>/g)?.length ?? 0).toBe(
      VALIDATABLE_PROVIDERS.length,
    );
  });

  it("renders password-type inputs with provider-specific placeholder text", () => {
    const html = renderPanel();
    for (const provider of VALIDATABLE_PROVIDERS) {
      expect(html).toContain(`placeholder="${provider} API key"`);
    }
  });
});
