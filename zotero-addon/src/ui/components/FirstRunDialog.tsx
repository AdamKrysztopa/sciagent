import { useState } from "react";

import { SCIAGENT_SERVER_VERSION } from "../../host/serverManager";
import type { AddonUiServices } from "../serviceTypes";

type DownloadPhase = "idle" | "downloading" | "starting" | "error";

interface FirstRunDialogProps {
  services: AddonUiServices;
  onComplete: () => void;
  onSkip: () => void;
}

export function FirstRunDialog({ services, onComplete, onSkip }: FirstRunDialogProps) {
  const [phase, setPhase] = useState<DownloadPhase>("idle");
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);

  async function handleDownload() {
    setPhase("downloading");
    setProgress(0);
    setError(null);
    try {
      await services.downloadBinary?.(SCIAGENT_SERVER_VERSION, setProgress);
      setPhase("starting");
      await services.startServerAfterDownload?.();
      onComplete();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setPhase("error");
    }
  }

  return (
    <div className="agt-state-view">
      <section className="agt-card" role="dialog" aria-labelledby="agt-first-run-heading">
        <div className="agt-section-heading">
          <h2 id="agt-first-run-heading">Set Up SciAgent Server</h2>
        </div>
        <p className="agt-small-note">
          The SciAgent backend binary is not installed. Download it once (~70 MB) to run
          searches locally — no internet connection required after install.
        </p>
        <p className="agt-small-note agt-meta">Version: {SCIAGENT_SERVER_VERSION}</p>

        {phase === "idle" && (
          <div className="agt-action-cluster">
            <button
              className="agt-button agt-button--warn"
              onClick={() => void handleDownload()}
              type="button"
            >
              Download Server
            </button>
            <button
              className="agt-button agt-button--ghost"
              onClick={onSkip}
              type="button"
            >
              Use Remote Backend
            </button>
          </div>
        )}

        {phase === "downloading" && (
          <>
            <div
              aria-label={`Downloading: ${progress}%`}
              aria-valuemax={100}
              aria-valuemin={0}
              aria-valuenow={progress}
              className="agt-progress-bar"
              role="progressbar"
            >
              <div className="agt-progress-fill" style={{ width: `${progress}%` }} />
            </div>
            <p className="agt-small-note">{progress}% downloaded…</p>
          </>
        )}

        {phase === "starting" && (
          <div className="agt-spinner-wrap">
            <div className="agt-spinner" />
            <p className="agt-meta">Starting server…</p>
          </div>
        )}

        {phase === "error" && (
          <>
            <div className="agt-error">{error}</div>
            <div className="agt-action-cluster">
              <button
                className="agt-button agt-button--warn"
                onClick={() => void handleDownload()}
                type="button"
              >
                Retry
              </button>
              <button
                className="agt-button agt-button--ghost"
                onClick={onSkip}
                type="button"
              >
                Use Remote Backend
              </button>
            </div>
          </>
        )}
      </section>
    </div>
  );
}
