"""Vendor the crinetics-tlf-automation library into the backend.

Copies the parts of the sibling automation repo that the Studio backend
imports at runtime — the ``tlf`` Python package plus the shell registry and
default study-config template — into ``backend/vendor/`` so the app is
self-contained (no sibling-folder lookup, freezable with PyInstaller).

Run this after changing the automation repo to refresh the vendored copy:

    uv run python scripts/vendor_tlf.py
    uv run python scripts/vendor_tlf.py --source ../crinetics-tlf-automation

The vendored copy preserves the library's directory layout
(``src/tlf`` + ``shells`` + ``config``) so tlf's REPO_ROOT-relative paths
still resolve correctly.
"""

from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path

# Subdirectories of the automation repo to vendor, relative to its root.
VENDOR_PARTS = ["src/tlf", "shells", "config"]

STUDIO_ROOT = Path(__file__).resolve().parents[1]
VENDOR_DIR = STUDIO_ROOT / "backend" / "vendor"


def _default_source() -> Path:
    env = os.environ.get("TLF_AUTOMATION_PATH")
    if env:
        return Path(env)
    return STUDIO_ROOT.parent / "crinetics-tlf-automation"


def _ignore(_dir: str, names: list[str]) -> set[str]:
    """Skip caches and compiled artefacts when copying."""
    drop = {"__pycache__", ".pytest_cache", ".mypy_cache"}
    return {n for n in names if n in drop or n.endswith((".pyc", ".pyo"))}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        default=_default_source(),
        help="Path to the crinetics-tlf-automation checkout.",
    )
    args = parser.parse_args()

    source: Path = args.source.resolve()
    if not source.exists():
        print(f"ERROR: automation repo not found: {source}")
        print("Pass --source <path> or set TLF_AUTOMATION_PATH.")
        return 1

    for part in VENDOR_PARTS:
        src = source / part
        if not src.exists():
            print(f"ERROR: expected {src} in the automation repo.")
            return 1

    if VENDOR_DIR.exists():
        shutil.rmtree(VENDOR_DIR)
    VENDOR_DIR.mkdir(parents=True)

    for part in VENDOR_PARTS:
        src = source / part
        dst = VENDOR_DIR / part
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, dst, ignore=_ignore)
        print(f"  vendored {part}")

    # Record the source commit for traceability, if available.
    head = source / ".git" / "HEAD"
    stamp = VENDOR_DIR / "VENDOR_INFO.txt"
    lines = [f"source: {source}"]
    try:
        ref = head.read_text().strip()
        if ref.startswith("ref:"):
            ref_path = source / ".git" / ref.split(" ", 1)[1].strip()
            if ref_path.exists():
                lines.append(f"commit: {ref_path.read_text().strip()}")
    except Exception:
        pass
    stamp.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Vendored tlf into {VENDOR_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
