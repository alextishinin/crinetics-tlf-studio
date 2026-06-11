"""Helpers for adapting tlf-library configs to a Studio study directory."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any


_ADAM_SUFFIXES = {".parquet", ".sas7bdat", ".xpt"}

# Serialises every call into the tlf library within this process. The library
# keeps process-global state (validator shell mode set per study by
# configure_for_study) and the preview service temporarily swaps the
# render_table binding across modules — so two studies' generation/preview
# requests must never interleave inside the library, or one study's tables
# can render with the other's shell-mode placeholders (or get captured by a
# concurrent preview instead of writing the RTF).
TLF_LOCK = threading.RLock()


def configure_for_study(cfg: Any, study_dir: Path) -> None:
    """Point a tlf StudyConfig at this Studio study's data and outputs.

    The tlf library computes ``shell_mode`` while loading the YAML, before
    Studio has replaced the default ADaM path with the uploaded study data
    directory. Recompute it here so uploaded parquet files generate real
    counts instead of shell placeholders.
    """
    data_dir = (study_dir / "data").resolve()
    output_dir = (study_dir / "outputs").resolve()

    cfg.adam_path = data_dir
    cfg.output_path = output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    has_uploaded_data = any(
        p.is_file() and p.suffix.lower() in _ADAM_SUFFIXES
        for p in data_dir.iterdir()
    ) if data_dir.exists() else False
    cfg.shell_mode = not has_uploaded_data

    try:
        from tlf.validator import set_shell_mode
    except Exception:
        return
    set_shell_mode(cfg.shell_mode)
