import {
  REQUIRED_API_CONTRACT_VERSION,
  validateContractVersion,
  type HealthResponse,
} from "../../shared/contracts";

interface HealthStatusProps {
  busy: boolean;
  error: string | null;
  onRefresh(): void;
  response: HealthResponse | null;
}

function healthClassName(busy: boolean, response: HealthResponse | null, error: string | null): string {
  if (busy) {
    return "agt-pill agt-pill--loading";
  }
  if (error !== null) {
    return "agt-pill agt-pill--error";
  }
  if (response?.ok) {
    return "agt-pill agt-pill--ok";
  }
  if (response !== null) {
    return "agt-pill agt-pill--warn";
  }
  return "agt-pill agt-pill--idle";
}

function healthLabel(busy: boolean, response: HealthResponse | null, error: string | null): string {
  if (busy) {
    return "Checking backend";
  }
  if (error !== null) {
    return "Backend error";
  }
  if (response?.ok) {
    return "Backend healthy";
  }
  if (response !== null) {
    return "Backend reachable";
  }
  return "Health not checked";
}

export function HealthStatus({ busy, error, onRefresh, response }: HealthStatusProps) {
  const contractStatus = validateContractVersion(response);
  const showContractWarning = response !== null && contractStatus !== "compatible";
  const showPreflightWarning = response !== null && !response.ok;

  return (
    <section className="agt-card agt-card--soft">
      <div className="agt-section-heading">
        <h2>Backend Health</h2>
        <div className="agt-inline-actions">
          <span className={healthClassName(busy, response, error)}>{healthLabel(busy, response, error)}</span>
          <button className="agt-button agt-button--ghost" disabled={busy} onClick={onRefresh} type="button">
            {busy ? "Checking..." : "Refresh"}
          </button>
        </div>
      </div>
      {showContractWarning ? (
        <div className="agt-error">
          {contractStatus === "missing"
            ? `Backend contract version missing. Expected ${REQUIRED_API_CONTRACT_VERSION}.`
            : `Backend contract version mismatch. Expected ${REQUIRED_API_CONTRACT_VERSION}, got ${response.api_contract_version}.`}
        </div>
      ) : null}
      {response !== null ? (
        <div className="agt-key-value">
          <span>Provider</span>
          <span>{response.provider}</span>
          <span>Fallback</span>
          <span>{response.fallback_provider ?? "none"}</span>
          <span>Preflight</span>
          <span>{response.preflight.message ?? response.message}</span>
        </div>
      ) : null}
      {showPreflightWarning ? (
        <output className="agt-status-note agt-status-note--warn" aria-live="polite">
          Backend is online, but preflight needs attention: {response.preflight.message ?? response.message}
        </output>
      ) : null}
      {response === null && error === null ? (
        <p className="agt-empty-state">Waiting for the first backend health response.</p>
      ) : null}
      {error !== null ? <div className="agt-error">{error}</div> : null}
    </section>
  );
}
