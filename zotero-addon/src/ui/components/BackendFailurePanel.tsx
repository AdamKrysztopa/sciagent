interface BackendFailurePanelProps {
  error: string;
  onRetry(): void;
}

export function BackendFailurePanel({ error, onRetry }: BackendFailurePanelProps) {
  return (
    <section className="agt-card agt-startup-error" role="alert">
      <h2>Backend unavailable</h2>
      <p className="agt-meta">{error}</p>
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
      <button
        className="agt-button agt-button--warn"
        onClick={onRetry}
        type="button"
      >
        Retry connection
      </button>
      <p className="agt-small-note">
        Open Preferences → Connection &amp; Auth to change the backend URL
      </p>
    </section>
  );
}
