interface BackendFailurePanelProps {
  error: string;
  onRetry(): void;
  backendMode?: string;
}

export function BackendFailurePanel({ error, onRetry, backendMode }: BackendFailurePanelProps) {
  const isLocal = backendMode === "local";

  return (
    <section className="agt-card agt-startup-error" role="alert">
      <h2>Backend unavailable</h2>
      <p className="agt-meta">{error}</p>
      {isLocal ? (
        <ol>
          <li>Make sure at least one LLM provider key is set in <strong>Preferences → LLM Provider</strong></li>
          <li>If this is a fresh install, close and reopen the SciAgent panel — the server may still be starting</li>
          <li>If the binary is missing, reinstall the add-on and let the first-run dialog download it again</li>
        </ol>
      ) : (
        <ol>
          <li>Verify the Backend URL in Preferences matches where the server is running</li>
          <li>
            Start the backend manually:{" "}
            <code>uv run python -m agt.api.app</code> or run the{" "}
            <code>sciagent-server</code> binary
          </li>
          <li>
            Use Docker:{" "}
            <code>docker run -p 8000:8000 ghcr.io/adamkrysztopa/sciagent</code>
          </li>
        </ol>
      )}
      <button
        className="agt-button agt-button--warn"
        onClick={onRetry}
        type="button"
      >
        Retry connection
      </button>
      {!isLocal && (
        <p className="agt-small-note">
          Open Preferences → Connection &amp; Auth to change the backend URL
        </p>
      )}
    </section>
  );
}
