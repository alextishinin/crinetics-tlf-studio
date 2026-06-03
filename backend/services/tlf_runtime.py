"""Helpers for adapting tlf-library configs to a Studio study directory."""

from __future__ import annotations

from pathlib import Path
from typing import Any


_ADAM_SUFFIXES = {".parquet", ".sas7bdat", ".xpt"}


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
