export interface CapabilityBannerProps {
  backendOk: boolean;
  llmProviderOk: boolean;
  zoteroWriteOk: boolean;
  pdfImportOk: boolean;
  onDismiss(): void;
}

interface CheckRowProps {
  ok: boolean;
  label: string;
  hint: string;
}

function CheckRow({ ok, label, hint }: CheckRowProps) {
  return (
    <div className="agt-capability-row">
      <span className={ok ? "agt-check--ok" : "agt-check--fail"} aria-hidden="true">
        {ok ? "✓" : "✗"}
      </span>
      <span className="agt-capability-label">{label}</span>
      {!ok ? (
        <span className="agt-small-note agt-small-note--warn">{hint}</span>
      ) : null}
    </div>
  );
}

export function CapabilityBanner({
  backendOk,
  llmProviderOk,
  zoteroWriteOk,
  pdfImportOk,
  onDismiss,
}: CapabilityBannerProps) {
  const allOk = backendOk && llmProviderOk && zoteroWriteOk && pdfImportOk;

  return (
    <section className="agt-card agt-card--soft" aria-label="SciAgent setup checklist">
      <div className="agt-section-heading">
        <h2>SciAgent Setup</h2>
      </div>

      <CheckRow
        ok={backendOk}
        label="Backend reachable"
        hint="Check Backend URL in Preferences → Connection & Auth"
      />
      <CheckRow
        ok={llmProviderOk}
        label="LLM provider configured"
        hint="Set an API key in Preferences → LLM Provider"
      />
      <CheckRow
        ok={zoteroWriteOk}
        label="Zotero write access"
        hint="Verify your Zotero API key at zotero.org/settings/keys"
      />
      <CheckRow
        ok={pdfImportOk}
        label="PDF import supported"
        hint="Enable in Preferences → Write Path"
      />

      {allOk ? (
        <span className="agt-pill agt-pill--ok">All checks passed</span>
      ) : null}

      <button
        className="agt-button agt-button--ghost agt-button--sm"
        onClick={onDismiss}
        type="button"
      >
        Dismiss
      </button>
    </section>
  );
}
