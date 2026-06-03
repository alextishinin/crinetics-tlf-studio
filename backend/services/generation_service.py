"""Dispatch generation requests to the tlf library and persist job records.

Job records are stored in `<study>/jobs.json` as an append-only list so the
filesystem alone is the source of truth (no separate database).

The actual table-generation calls map shell ids to the right tlf function;
the table modules in `crinetics-tlf-automation/src/tlf/tables/` are imported
on demand.
"""

from __future__ import annotations

import json
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from config import get_settings
from models.job import JobRecord, JobStatus
from services import study_service
from services.tlf_runtime import configure_for_study


JOBS_FILE = "jobs.json"


# ---------------------------------------------------------------------------
# Shell-id → tlf function mapping
# ---------------------------------------------------------------------------

def _dispatchers() -> dict[str, Callable[..., Any]]:
    """Return a mapping shell_id → function(cfg, registry, **kwargs).

    Imports happen inside the function so the studio backend can be unit-
    tested without the tlf library available.
    """
    from tlf.tables import (
        adverse_events,
        baseline,
        disposition,
        ecg,
        exposure,
        labs,
        vitals,
    )
    from tlf.figures import safety

    return {
        # Disposition / demographics / exposure
        "t_14_1_1_1":           lambda cfg, reg, **k: disposition.generate(cfg, reg, **k),
        "t_14_1_2_1":           lambda cfg, reg, **k: baseline.generate(cfg, reg, **k),
        "t_14_1_3_1":           lambda cfg, reg, **k: exposure.generate(cfg, reg, **k),
        "t_14_1_3_2":           lambda cfg, reg, **k: exposure.generate_compliance(cfg, reg, **k),
        # Adverse events
        "t_14_3_1_1":           lambda cfg, reg, **k: adverse_events.generate_overview(cfg, reg, **k),
        "t_14_3_1_2":           lambda cfg, reg, **k: adverse_events.generate_soc_pt(cfg, reg, shell_id="t_14_3_1_2", **k),
        "t_14_3_1_5":           lambda cfg, reg, **k: adverse_events.generate_soc_pt(cfg, reg, shell_id="t_14_3_1_5", **k),
        "t_14_3_1_6":           lambda cfg, reg, **k: adverse_events.generate_soc_pt(cfg, reg, shell_id="t_14_3_1_6", **k),
        "t_14_3_1_7":           lambda cfg, reg, **k: adverse_events.generate_soc_pt(cfg, reg, shell_id="t_14_3_1_7", **k),
        "t_14_3_1_8":           lambda cfg, reg, **k: adverse_events.generate_soc_pt(cfg, reg, shell_id="t_14_3_1_8", **k),
        "t_14_3_1_9":           lambda cfg, reg, **k: adverse_events.generate_pt_only(cfg, reg, shell_id="t_14_3_1_9", **k),
        "t_14_3_1_10":          lambda cfg, reg, **k: adverse_events.generate_pt_only(cfg, reg, shell_id="t_14_3_1_10", **k),
        "t_14_3_1_11_common":   lambda cfg, reg, **k: adverse_events.generate_pt_only(cfg, reg, shell_id="t_14_3_1_11_common", **k),
        "t_14_3_1_11_aesi":     lambda cfg, reg, **k: adverse_events.generate_aesi(cfg, reg, shell_id="t_14_3_1_11_aesi", **k),
        "t_14_3_1_12":          lambda cfg, reg, **k: adverse_events.generate_aesi(cfg, reg, shell_id="t_14_3_1_12", **k),
        "t_14_3_1_13":          lambda cfg, reg, **k: adverse_events.generate_severity(cfg, reg, **k),
        "t_14_3_1_14":          lambda cfg, reg, **k: adverse_events.generate_causality(cfg, reg, **k),
        # Labs
        "t_14_3_4_1":           lambda cfg, reg, **k: labs.generate_summary(cfg, reg, shell_id="t_14_3_4_1", **k),
        "t_14_3_4_2":           lambda cfg, reg, **k: labs.generate_summary(cfg, reg, shell_id="t_14_3_4_2", **k),
        "t_14_3_4_3":           lambda cfg, reg, **k: labs.generate_abnormality(cfg, reg, shell_id="t_14_3_4_3", **k),
        "t_14_3_4_4":           lambda cfg, reg, **k: labs.generate_abnormality(cfg, reg, shell_id="t_14_3_4_4", **k),
        "t_14_3_4_5":           lambda cfg, reg, **k: labs.generate_specific_levels(cfg, reg, shell_id="t_14_3_4_5", **k),
        "t_14_3_4_6":           lambda cfg, reg, **k: labs.generate_specific_levels(cfg, reg, shell_id="t_14_3_4_6", **k),
        # Vitals + ECG
        "t_14_3_5_1":           lambda cfg, reg, **k: vitals.generate(cfg, reg, **k),
        "t_14_3_5_2":           lambda cfg, reg, **k: vitals.generate_bp_levels(cfg, reg, **k),
        "t_14_3_6_1":           lambda cfg, reg, **k: ecg.generate_summary(cfg, reg, **k),
        "t_14_3_6_2":           lambda cfg, reg, **k: ecg.generate_qtcf_criteria(cfg, reg, **k),
        # Figures
        "f_14_1_1_1":           lambda cfg, reg, **k: safety.generate_time_to_disc(cfg, reg, **k),
        "f_14_3_1_1":           lambda cfg, reg, **k: safety.generate_ae_forest(cfg, reg, **k),
        "f_14_3_4_1":           lambda cfg, reg, **k: safety.generate_lab_cfb(cfg, reg, domain="adlbc", shell_id="f_14_3_4_1", **k),
        "f_14_3_4_2":           lambda cfg, reg, **k: safety.generate_lab_cfb(cfg, reg, domain="adlbh", shell_id="f_14_3_4_2", **k),
        "f_14_3_4_3":           lambda cfg, reg, **k: safety.generate_hys_law(cfg, reg, **k),
        "f_14_3_5_1":           lambda cfg, reg, **k: safety.generate_bp_over_time(cfg, reg, **k),
        "f_14_3_5_2":           lambda cfg, reg, **k: safety.generate_bp_baseline_vs_max(cfg, reg, **k),
    }


# ---------------------------------------------------------------------------
# Job record persistence
# ---------------------------------------------------------------------------

def _jobs_path(study_id: str) -> Path:
    return study_service.study_dir(study_id) / JOBS_FILE


def _read_jobs(study_id: str) -> list[dict[str, Any]]:
    path = _jobs_path(study_id)
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return []


def _write_jobs(study_id: str, jobs: list[dict[str, Any]]) -> None:
    _jobs_path(study_id).write_text(json.dumps(jobs, indent=2, default=str))


def submit(study_id: str, table_ids: list[str], *, triggered_by: str = "user") -> list[JobRecord]:
    """Create job records (status=queued) and return them. The dispatch to
    Celery happens in the router so we can avoid importing the worker
    module in unit tests."""
    now = datetime.now(tz=timezone.utc)
    batch_id = str(uuid.uuid4()) if len(table_ids) > 1 else None
    records: list[JobRecord] = []
    for table_id in table_ids:
        rec = JobRecord(
            job_id=str(uuid.uuid4()),
            study_id=study_id,
            table_id=table_id,
            table_number=table_id.replace("t_", "").replace("f_", "").replace("_", "."),
            status=JobStatus.QUEUED,
            submitted_at=now,
            triggered_by=triggered_by,
            batch_id=batch_id,
        )
        records.append(rec)
    # Append to jobs.json
    existing = _read_jobs(study_id)
    existing.extend([r.model_dump(mode="json") for r in records])
    _write_jobs(study_id, existing)
    return records


def list_jobs(study_id: str) -> list[JobRecord]:
    return [JobRecord.model_validate(r) for r in _read_jobs(study_id)]


def get_job(study_id: str, job_id: str) -> JobRecord:
    for r in _read_jobs(study_id):
        if r.get("job_id") == job_id:
            return JobRecord.model_validate(r)
    raise KeyError(f"Job {job_id} not found")


def update_job(study_id: str, job_id: str, **patch: Any) -> JobRecord:
    jobs = _read_jobs(study_id)
    found = None
    for r in jobs:
        if r.get("job_id") == job_id:
            r.update({k: (v if not isinstance(v, datetime) else v.isoformat()) for k, v in patch.items()})
            found = r
            break
    if found is None:
        raise KeyError(f"Job {job_id} not found")
    _write_jobs(study_id, jobs)
    return JobRecord.model_validate(found)


def cancel_job(study_id: str, job_id: str) -> JobRecord:
    return update_job(study_id, job_id, status=JobStatus.CANCELLED.value)


# ---------------------------------------------------------------------------
# Inline execution path (used by tests + as the Celery task body)
# ---------------------------------------------------------------------------

def run_inline(study_id: str, job_id: str) -> JobRecord:
    """Execute one generation synchronously (used by tests + by Celery)."""
    record = get_job(study_id, job_id)
    update_job(
        study_id, job_id,
        status=JobStatus.RUNNING.value,
        started_at=datetime.now(tz=timezone.utc),
    )
    try:
        out_path = _do_generate(study_id, record.table_id)
        return update_job(
            study_id, job_id,
            status=JobStatus.COMPLETE.value,
            completed_at=datetime.now(tz=timezone.utc),
            output_path=str(out_path),
        )
    except Exception as exc:
        tb = traceback.format_exc()
        return update_job(
            study_id, job_id,
            status=JobStatus.FAILED.value,
            completed_at=datetime.now(tz=timezone.utc),
            error=f"{type(exc).__name__}: {exc}\n{tb}",
        )


def _do_generate(study_id: str, table_id: str) -> Path:
    """Bridge from a shell id to the matching tlf-library function call."""
    from tlf.config import load_shell_registry, load_study_config

    sdir = study_service.study_dir(study_id)
    cfg = load_study_config(sdir / "study_config.yaml")
    settings = get_settings()
    registry = load_shell_registry(settings.tlf_registry_path)

    # Point the cfg at this study's data / outputs and recompute shell_mode
    # after those paths are known.
    configure_for_study(cfg, sdir)

    dispatch = _dispatchers()
    if table_id not in dispatch:
        raise ValueError(f"Unknown table id: {table_id}")
    return Path(dispatch[table_id](cfg, registry))
