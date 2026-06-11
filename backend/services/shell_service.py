"""Shell registry loading + conditionality resolution.

The registry itself lives in the tlf automation project. This service:
  - Loads it once and caches in-process
  - Decorates each shell with current study state: whether the required
    ADaM domains are present, whether condition-driven shells should be
    auto-selected, and whether the user has saved a selection
  - Groups shells for the sidebar UI
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import polars as pl
import yaml

from config import get_settings
from models.shell import (
    Conditionality,
    ShellEntry,
    ShellGroup,
    ShellListResponse,
)
from services import study_service
from services.adam_service import read_dataset
from services.shell_ids import table_number as _shell_table_number

# Every ADaM file format the upload pipeline accepts. Conditionality checks
# must look across all of them — checking only *.parquet silently deselected
# conditional shells for studies uploaded as SAS7BDAT/XPT.
_DATA_SUFFIXES = (".parquet", ".sas7bdat", ".xpt")


def _find_dataset(data_dir: Path, stem: str) -> Path | None:
    for ext in _DATA_SUFFIXES:
        p = data_dir / f"{stem}{ext}"
        if p.exists():
            return p
    return None


# Domain group labels for the left-side sidebar in the TFL selection screen.
_GROUP_LABELS = [
    ("Subject Disposition & Analysis Sets", lambda s: s["id"].startswith("t_14_1_1")),
    ("Demographics & Baseline Characteristics", lambda s: s["id"].startswith("t_14_1_2")),
    ("Extent of Exposure", lambda s: s["id"].startswith("t_14_1_3")),
    ("Adverse Events", lambda s: s["id"].startswith("t_14_3_1")),
    ("Clinical Laboratory (Chemistry)", lambda s: s["id"] in {"t_14_3_4_1", "t_14_3_4_3", "t_14_3_4_5"}),
    ("Clinical Laboratory (Hematology)", lambda s: s["id"] in {"t_14_3_4_2", "t_14_3_4_4", "t_14_3_4_6"}),
    ("Vital Signs", lambda s: s["id"].startswith("t_14_3_5")),
    ("Electrocardiogram", lambda s: s["id"].startswith("t_14_3_6")),
    ("Figures — Safety", lambda s: s["type"] == "figure"),
    ("Generic / Efficacy Layouts", lambda s: s["type"] == "generic_layout"),
]


@lru_cache(maxsize=1)
def load_registry() -> dict[str, Any]:
    path = get_settings().tlf_registry_path.resolve()
    with open(path) as f:
        registry = yaml.safe_load(f) or {}
    if registry.get("shell_files"):
        shells: list[dict[str, Any]] = []
        for rel in registry["shell_files"]:
            shell_path = path.parent / rel
            with open(shell_path) as f:
                shell = yaml.safe_load(f) or {}
            if "id" not in shell:
                raise ValueError(f"Shell file {shell_path} is missing required key 'id'")
            shells.append(shell)
        registry["shells"] = shells
    else:
        registry["shells"] = registry.get("shells", [])
    return registry


def clear_cache() -> None:
    load_registry.cache_clear()


def _group_for(shell: dict[str, Any]) -> str:
    for label, predicate in _GROUP_LABELS:
        try:
            if predicate(shell):
                return label
        except Exception:
            continue
    return "Other"


def _table_number(shell: dict[str, Any]) -> str:
    """'t_14_1_1_1' -> '14.1.1.1'; 't_14_3_1_11_common' -> '14.3.1.11 (common)'."""
    return _shell_table_number(shell["id"])


def _domains_available(shell: dict[str, Any], present: set[str]) -> tuple[bool, str | None]:
    """Are all required ADaM domains present for this shell?"""
    required = set(shell.get("adam_domains", []) or [])
    missing = sorted(required - present)
    if missing:
        return False, f"Requires {', '.join(missing)} which is not uploaded."
    return True, None


# ---------------------------------------------------------------------------
# Conditionality resolution
# ---------------------------------------------------------------------------

def _resolve_condition(
    shell: dict[str, Any],
    config: dict[str, Any],
    data_dir: Path,
) -> tuple[bool, str | None]:
    """Return (should_auto_select, explanation).

    `should_auto_select` is meaningful only when the shell's conditionality
    is 'conditional'. For 'required' it's always True; for 'optional' it
    follows the optional_outputs flag (caller handles that).
    """
    sid = shell["id"]
    # Heuristics for known conditional outputs:
    if sid == "t_14_3_1_8":   # Fatal AEs
        return _conditional_on_flag(data_dir, "adsl", "DTHFL", "Y",
                                    explanation="DTHFL='Y' present in ADSL.")
    if sid == "t_14_3_1_7":   # AEs leading to discontinuation
        return _conditional_on_flag(data_dir, "adsl", "DSRAEFL", "Y",
                                    explanation="DSRAEFL='Y' present in ADSL.")
    if sid == "f_14_3_4_3":   # Hy's Law
        if _find_dataset(data_dir, "adlbhy") is not None:
            return True, "ADLBHY available; potential Hy's Law cases will be plotted."
        return False, "ADLBHY not uploaded."
    return False, None


def _conditional_on_flag(
    data_dir: Path,
    stem: str,
    var: str,
    val: str,
    *,
    explanation: str,
) -> tuple[bool, str | None]:
    path = _find_dataset(data_dir, stem)
    if path is None:
        return False, f"{stem} not uploaded."
    try:
        df = read_dataset(path)
    except Exception as exc:
        return False, f"Could not read {path.name}: {exc}"
    if var not in df.columns:
        return False, f"{var} not in {path.name}."
    has_any = df.filter(pl.col(var) == val).height > 0
    if has_any:
        return True, explanation
    return False, f"No {var}='{val}' rows in {path.name}."


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def list_for_study(study_id: str) -> ShellListResponse:
    """Build the full ShellListResponse for the TFL selection screen.

    Auto-selection rules:
      - Required shells: selected=True, available depends on uploaded data
      - Conditional shells: auto-set selected based on _resolve_condition()
      - Optional shells: selected = config.optional_outputs.get(flag, False)
    """
    registry = load_registry()
    config = study_service.read_config(study_id)
    data_dir = study_service.study_dir(study_id) / "data"
    optional_outputs = config.get("optional_outputs", {}) or {}

    # Inventory of uploaded ADaM domains (filename stem without extension).
    present: set[str] = set()
    if data_dir.exists():
        for p in data_dir.iterdir():
            if p.suffix.lower() in (".parquet", ".sas7bdat", ".xpt"):
                present.add(p.stem.lower())

    groups: dict[str, list[ShellEntry]] = {label: [] for label, _ in _GROUP_LABELS}
    auto_selected: list[str] = []
    auto_deselected: list[str] = []

    for shell in registry.get("shells", []):
        cond = Conditionality(shell.get("conditionality", "required"))
        available, avail_reason = _domains_available(shell, present)

        if cond == Conditionality.REQUIRED:
            selected = available
            condition_reason = avail_reason
        elif cond == Conditionality.CONDITIONAL:
            auto, reason = _resolve_condition(shell, config, data_dir)
            selected = available and auto
            condition_reason = reason
            if available:
                (auto_selected if selected else auto_deselected).append(shell["id"])
        else:  # OPTIONAL
            flag = shell.get("optional_flag")
            saved = bool(optional_outputs.get(flag)) if flag else False
            selected = available and saved
            condition_reason = avail_reason

        title3 = shell.get("title_line3", "")
        entry = ShellEntry(
            id=shell["id"],
            type=shell.get("type", "table"),
            table_number=_table_number(shell),
            title_line1=shell.get("title_line1", ""),
            title_line2=shell.get("title_line2", ""),
            title_line3=title3,
            population=title3,
            adam_domains=list(shell.get("adam_domains", []) or []),
            domain_group=_group_for(shell),
            conditionality=cond,
            optional_flag=shell.get("optional_flag"),
            selected=selected,
            available=available,
            condition_reason=condition_reason,
        )
        groups[entry.domain_group].append(entry)

    return ShellListResponse(
        groups=[ShellGroup(name=name, shells=shells) for name, shells in groups.items() if shells],
        auto_selected=auto_selected,
        auto_deselected=auto_deselected,
    )


def save_selections(study_id: str, optional_outputs: dict[str, bool]) -> dict[str, bool]:
    """Persist optional_outputs into the study's config.yaml."""
    config = study_service.read_config(study_id)
    config["optional_outputs"] = {**(config.get("optional_outputs") or {}), **optional_outputs}
    from services.study_service import _write_config, study_dir
    _write_config(study_dir(study_id), config)
    return config["optional_outputs"]
