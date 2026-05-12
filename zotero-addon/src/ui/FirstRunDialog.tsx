import { useState } from "react";

import { downloadBinary } from "../host/serverManager";

interface Props {
  version: string;
  onComplete: () => void;
  onError: (msg: string) => void;
}

type Status = "ready" | "downloading" | "done" | "error";

export function FirstRunDialog({ version, onComplete, onError }: Props) {
  const [progress, setProgress] = useState<number | null>(null);
  const [status, setStatus] = useState<Status>("ready");

  async function handleInstall() {
    setStatus("downloading");
    try {
      await downloadBinary(version, (pct) => setProgress(pct));
      setStatus("done");
      onComplete();
    } catch (e: unknown) {
      setStatus("error");
      onError(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <div style={{ padding: 24, maxWidth: 420 }}>
      <h2>Welcome to SciAgent</h2>
      <p style={{ color: "#555" }}>
        SciAgent needs to download its search engine (~70 MB, one time only). Everything runs on
        your computer — your data stays local.
      </p>
      {status === "ready" && (
        <button onClick={() => void handleInstall()} type="button">
          Download &amp; Install
        </button>
      )}
      {status === "downloading" && (
        <div>
          <progress max={100} style={{ width: "100%" }} value={progress ?? 0} />
          <p>{progress !== null ? `${progress}%` : "Starting…"}</p>
        </div>
      )}
      {status === "done" && <p>Ready. You can close this window.</p>}
      {status === "error" && <p>Download failed. Check your internet connection.</p>}
    </div>
  );
}
