"""Filesystem-backed study storage.

Each study is a directory under STUDIES_ROOT containing:

    {study_id}/
        study_meta.json         — app-level metadata (title, status, timestamps)
        study_config.yaml       — tlf library config (drives generation)
        data/                   — uploaded ADaM datasets
        outputs/                — generated RTF/PNG files
        audit/                  — per-output audit JSON
        jobs.json               — append-only job record store
        shell_selection.json    — cached shell selection diff (informational)
"""

from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from config import get_settings
from models.study import (
    StudyCreate,
    StudyDetail,
    StudyMeta,
    StudyStatus,
    StudySummary,
    StudyUpdate,
)


STUDY_CONFIG_NAME = "study_config.yaml"
STUDY_META_NAME = "study_meta.json"


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def studies_root() -> Path:
    root = get_settings().studies_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def study_dir(study_id: str) -> Path:
    """Return the study directory; raise FileNotFoundError if missing."""
    path = studies_root() / study_id
    if not path.exists():
        raise FileNotFoundError(f"Study {study_id} not found")
    return path


def _new_study_dir(study_id: str) -> Path:
    path = studies_root() / study_id
    (path / "data").mkdir(parents=True, exist_ok=True)
    (path / "outputs").mkdir(parents=True, exist_ok=True)
    (path / "audit").mkdir(parents=True, exist_ok=True)
    return path


# ---------------------------------------------------------------------------
# Default config seed
# ---------------------------------------------------------------------------

def _seed_config(create: StudyCreate) -> dict[str, Any]:
    """Return a starting study_config dict.

    Pulls structure from the tlf automation reference config when available
    so new studies inherit sensible defaults (exposure bins, common AE
    cutoff, optional_outputs map). Per-study identifiers are overridden.
    """
    settings = get_settings()
    template_path = settings.tlf_default_config_path.resolve()
    if template_path.exists():
        with open(template_path) as f:
            base = yaml.safe_load(f) or {}
    else:
        base = {}

    base["study_id"] = create.protocol_number or "NEW_STUDY"
    base["protocol_number"] = create.protocol_number or base["study_id"]
    base["protocol_title"] = create.title
    base["indication"] = create.indication or base.get("indication", "")
    # Wipe per-study identifiers from the template
    base["data_extract_date"] = ""
    base["data_cut_date"] = ""
    base["run_datetime"] = ""
    return base


# ---------------------------------------------------------------------------
# Create / read / update / delete
# ---------------------------------------------------------------------------

def create_study(payload: StudyCreate) -> StudyDetail:
    study_id = str(uuid.uuid4())
    now = datetime.now(tz=timezone.utc)
    path = _new_study_dir(study_id)
    meta = StudyMeta(
        study_id=study_id,
        title=payload.title,
        drug=payload.drug,
        indication=payload.indication,
        status=StudyStatus.DRAFT,
        created_at=now,
        updated_at=now,
    )
    config = _seed_config(payload)
    _write_meta(path, meta)
    _write_config(path, config)
    return StudyDetail(meta=meta, config=config)


def read_meta(study_id: str) -> StudyMeta:
    path = study_dir(study_id) / STUDY_META_NAME
    with open(path) as f:
        return StudyMeta.model_validate_json(f.read())


def read_config(study_id: str) -> dict[str, Any]:
    path = study_dir(study_id) / STUDY_CONFIG_NAME
    with open(path) as f:
        return yaml.safe_load(f) or {}


def read_detail(study_id: str) -> StudyDetail:
    return StudyDetail(meta=read_meta(study_id), config=read_config(study_id))


def list_studies() -> list[StudySummary]:
    out: list[StudySummary] = []
    for child in sorted(studies_root().iterdir()):
        if not child.is_dir():
            continue
        meta_path = child / STUDY_META_NAME
        if not meta_path.exists():
            continue
        try:
            meta = StudyMeta.model_validate_json(meta_path.read_text())
            config = yaml.safe_load((child / STUDY_CONFIG_NAME).read_text()) or {}
        except Exception:
            # Skip corrupt entries; admin can clean these up out-of-band.
            continue
        arms = config.get("treatment_arms", []) or []
        analysis_sets = config.get("analysis_sets", {}) or {}
        saf_n = (analysis_sets.get("SAF", {}) or {}).get("n", {}) or {}
        total_n = sum(int(v or 0) for v in saf_n.values())
        optional_outputs = config.get("optional_outputs", {}) or {}
        selected_tables = sum(1 for v in optional_outputs.values() if v)
        out.append(
            StudySummary(
                study_id=meta.study_id,
                title=meta.title,
                protocol_number=config.get("protocol_number", ""),
                drug=meta.drug,
                indication=meta.indication,
                status=meta.status,
                n_arms=len(arms),
                total_n=total_n,
                selected_tables=selected_tables,
                available_tables=len(optional_outputs),
                last_generated_at=meta.last_generated_at,
                updated_at=meta.updated_at,
            )
        )
    return out


def update_config(study_id: str, update: StudyUpdate) -> StudyDetail:
    config = read_config(study_id)
    patch = update.model_dump(exclude_unset=True, exclude_none=True)

    # treatment_arms / analysis_sets / sap_definitions arrive as Pydantic
    # models; serialise back to plain dicts for YAML.
    if "treatment_arms" in patch:
        patch["treatment_arms"] = [a if isinstance(a, dict) else a.model_dump() for a in patch["treatment_arms"]]
    if "analysis_sets" in patch:
        patch["analysis_sets"] = {
            k: (v if isinstance(v, dict) else v.model_dump())
            for k, v in patch["analysis_sets"].items()
        }
    if "sap_definitions" in patch:
        sap = patch["sap_definitions"]
        patch["sap_definitions"] = sap if isinstance(sap, dict) else sap.model_dump()

    config.update(patch)
    path = study_dir(study_id)
    _write_config(path, config)

    meta = read_meta(study_id)
    meta_updates: dict[str, Any] = {"updated_at": datetime.now(tz=timezone.utc)}
    # Keep meta.title in sync when the user renames the study via
    # protocol_title (the only "title-ish" field surfaced in the UI). The
    # dashboard card reads meta.title, so without this the rename would be
    # silently ignored from the user's POV.
    if "protocol_title" in patch and patch["protocol_title"]:
        meta_updates["title"] = patch["protocol_title"]
    if "drug" in patch:
        meta_updates["drug"] = patch["drug"]
    if "indication" in patch:
        meta_updates["indication"] = patch["indication"]
    meta = meta.model_copy(update=meta_updates)
    _write_meta(path, meta)
    return StudyDetail(meta=meta, config=config)


def update_meta(study_id: str, **kwargs: Any) -> StudyMeta:
    path = study_dir(study_id)
    meta = read_meta(study_id)
    fields = {**kwargs, "updated_at": datetime.now(tz=timezone.utc)}
    meta = meta.model_copy(update=fields)
    _write_meta(path, meta)
    return meta


def delete_study(study_id: str) -> None:
    path = study_dir(study_id)
    shutil.rmtree(path)


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _write_meta(path: Path, meta: StudyMeta) -> None:
    (path / STUDY_META_NAME).write_text(
        meta.model_dump_json(indent=2)
    )


def _write_config(path: Path, config: dict[str, Any]) -> None:
    (path / STUDY_CONFIG_NAME).write_text(
        yaml.safe_dump(config, sort_keys=False)
    )
