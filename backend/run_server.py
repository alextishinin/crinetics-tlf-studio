"""Frozen-app entrypoint: serve the FastAPI backend with uvicorn.

This is what PyInstaller freezes into ``backend.exe``. It runs the app
in-process (no --reload / no worker subprocesses, which don't survive
freezing) and forces a headless matplotlib backend so figure generation
works without a display.

Host/port are taken from the environment so the Electron shell can pick a
free port:

    TLF_STUDIO_HOST   (default 127.0.0.1)
    TLF_STUDIO_PORT   (default 8000)
"""

from __future__ import annotations

import os
import sys


def main() -> int:
    # Figures render via matplotlib's Agg backend — no GUI/Tk needed.
    os.environ.setdefault("MPLBACKEND", "Agg")

    host = os.environ.get("TLF_STUDIO_HOST", "127.0.0.1")
    try:
        port = int(os.environ.get("TLF_STUDIO_PORT", "8000"))
    except ValueError:
        port = 8000

    import uvicorn

    import main as app_module

    print(f"TLF Studio backend starting on http://{host}:{port}", flush=True)
    uvicorn.run(app_module.app, host=host, port=port, log_level="info")
    return 0


if __name__ == "__main__":
    sys.exit(main())
