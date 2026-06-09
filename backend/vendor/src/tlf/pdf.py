"""Convert generated RTF tables to PDF with a timeout.

The actual conversion is done by Microsoft Word through a helper process in
pdf_worker.py. This wrapper starts that helper, waits for it to finish, and
raises a clear error if Word fails or hangs too long.

The subprocess design matters because Word automation can sometimes block
forever on hidden dialogs or file locks. If that happens, this file can
stop waiting, clean up leftover Word processes, and let the main generation
run continue or report the failure.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


DEFAULT_TIMEOUT_S = 180


def rtf_to_pdf(rtf_path: Path, *, timeout_s: int = DEFAULT_TIMEOUT_S) -> Path:
    """Convert ``rtf_path`` to a PDF next to it.

    Returns the path of the new PDF. Raises ``RuntimeError`` on any
    failure — including Word hanging past ``timeout_s`` seconds.

    Side effect: on timeout, any leftover ``WINWORD.EXE`` processes are
    killed so the next conversion can start fresh.
    """
    rtf_path = rtf_path.resolve()
    pdf_path = rtf_path.with_suffix(".pdf")

    try:
        result = subprocess.run(
            [sys.executable, "-m", "tlf.pdf_worker", str(rtf_path), str(pdf_path)],
            timeout=timeout_s,
            capture_output=True,
            text=True,
        )
    except subprocess.TimeoutExpired as exc:
        _kill_word_processes()
        raise RuntimeError(
            f"PDF conversion timed out after {timeout_s}s for {rtf_path.name}"
        ) from exc

    if result.returncode != 0:
        # Worker printed the underlying exception to stderr; surface it.
        message = (result.stderr or result.stdout or "unknown error").strip()
        raise RuntimeError(
            f"PDF conversion failed for {rtf_path.name}: {message}"
        )

    if not pdf_path.exists():
        raise RuntimeError(
            f"PDF conversion reported success but no file was written: {pdf_path}"
        )

    return pdf_path


def _kill_word_processes() -> None:
    """Best-effort cleanup of orphan Word processes after a hang.

    Word can leave invisible zombies when the COM client dies mid-call.
    These hold file locks (``~$<filename>.rtf``) and refuse to release
    them until the process is gone, which blocks the next attempt.
    """
    # /F = force kill; /T = include child processes; /IM = by image name.
    for image in ("WINWORD.EXE", "WINWORD"):
        try:
            subprocess.run(
                ["taskkill", "/F", "/T", "/IM", image],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=10,
            )
        except Exception:
            pass
