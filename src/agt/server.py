"""CLI entrypoint for the embedded local server (SCI-0604).

PyInstaller freezes this module into a self-contained binary that the Zotero
add-on downloads on first run and spawns as a subprocess.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="SciAgent local backend")
    parser.add_argument("--port", type=int, default=57321)
    parser.add_argument("--data-dir", type=Path, default=Path.home() / ".sciagent")
    parser.add_argument("--log-level", default="warning")
    parser.add_argument("--version", action="version", version="%(prog)s 0.1.0")
    args = parser.parse_args()

    args.data_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("AGT_DATA_DIR", str(args.data_dir))

    import uvicorn  # noqa: PLC0415

    uvicorn.run(
        "agt.api.app:app",
        host="127.0.0.1",
        port=args.port,
        log_level=args.log_level,
        access_log=False,
    )


if __name__ == "__main__":
    main()
