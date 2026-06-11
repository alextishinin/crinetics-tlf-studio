"""Generation jobs endpoints."""

from __future__ import annotations

import os
import threading

from fastapi import APIRouter, HTTPException

from config import get_settings
from models.job import JobRecord, JobSubmitRequest, JobSubmitResponse
from services import generation_service


router = APIRouter(prefix="/api/studies", tags=["jobs"])


def _executor() -> str:
    """Job execution mode.

    "background" (default) — worker thread; submission returns immediately
    with the jobs queued and the frontend polls for progress. Running a
    25-table batch inside the HTTP request (the old behaviour) risked client
    timeouts and froze the submit call for minutes.
    "inline" — synchronous; used by the tests.
    "celery" — Redis-backed worker for multi-process deployments.

    The env var wins over settings so tests can force inline mode without
    touching .env files.
    """
    return (os.environ.get("TLF_JOB_EXECUTOR") or get_settings().tlf_job_executor).lower()


@router.post("/{study_id}/jobs", response_model=JobSubmitResponse)
def submit_jobs(study_id: str, payload: JobSubmitRequest) -> JobSubmitResponse:
    try:
        records = generation_service.submit(
            study_id, payload.table_ids, triggered_by=payload.triggered_by,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    executor = _executor()
    if executor == "celery":
        from tasks.generation import generate_one  # imports celery_app

        for rec in records:
            generate_one.delay(study_id, rec.job_id)
    elif executor == "inline":
        # Synchronous: run each job before responding. Used by tests and as
        # a single-process debugging mode.
        for rec in records:
            generation_service.run_inline(study_id, rec.job_id)
        records = [generation_service.get_job(study_id, r.job_id) for r in records]
    else:  # background (default)
        thread = threading.Thread(
            target=generation_service.run_batch,
            args=(study_id, [r.job_id for r in records]),
            name=f"tlf-batch-{study_id[:8]}",
            daemon=True,
        )
        thread.start()

    batch_id = records[0].batch_id if records else None
    return JobSubmitResponse(batch_id=batch_id, jobs=records)


@router.get("/{study_id}/jobs", response_model=list[JobRecord])
def list_jobs(study_id: str) -> list[JobRecord]:
    try:
        return generation_service.list_jobs(study_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{study_id}/jobs/{job_id}", response_model=JobRecord)
def get_job(study_id: str, job_id: str) -> JobRecord:
    try:
        return generation_service.get_job(study_id, job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{study_id}/jobs/{job_id}", response_model=JobRecord)
def cancel_job(study_id: str, job_id: str) -> JobRecord:
    """Mark a job cancelled.

    A queued job in a background batch is skipped when its turn comes; a job
    that is already running is NOT interrupted (the status just records the
    user's intent) — the UI labels this action "Dismiss" accordingly.
    """
    try:
        return generation_service.cancel_job(study_id, job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
