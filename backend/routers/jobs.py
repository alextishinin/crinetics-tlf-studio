"""Generation jobs endpoints."""

from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException

from models.job import JobRecord, JobSubmitRequest, JobSubmitResponse
from services import generation_service


router = APIRouter(prefix="/api/studies", tags=["jobs"])


# Tests run synchronously via the inline runner; in production this is set
# to "celery" so jobs hit Redis and the worker picks them up.
_EXECUTOR = os.environ.get("TLF_JOB_EXECUTOR", "inline").lower()


@router.post("/{study_id}/jobs", response_model=JobSubmitResponse)
def submit_jobs(study_id: str, payload: JobSubmitRequest) -> JobSubmitResponse:
    try:
        records = generation_service.submit(
            study_id, payload.table_ids, triggered_by=payload.triggered_by,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if _EXECUTOR == "celery":
        from tasks.generation import generate_one  # imports celery_app
        for rec in records:
            generate_one.delay(study_id, rec.job_id)
    else:
        # Synchronous fallback: run each job inline. Useful for tests and
        # for a single-process dev setup without a Redis/Celery worker.
        for rec in records:
            generation_service.run_inline(study_id, rec.job_id)
        records = [generation_service.get_job(study_id, r.job_id) for r in records]

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
    try:
        return generation_service.cancel_job(study_id, job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
