"""Pydantic models for table generation jobs."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobRecord(BaseModel):
    """One row in the job queue."""
    job_id: str
    study_id: str
    table_id: str                             # shell id, e.g. 't_14_3_1_2'
    table_number: str
    status: JobStatus
    submitted_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    output_path: str | None = None
    error: str | None = None
    triggered_by: str = "user"
    batch_id: str | None = None


class JobSubmitRequest(BaseModel):
    """Body of POST /studies/{id}/jobs.

    Submitting multiple table_ids creates a batch.
    """
    table_ids: list[str]
    triggered_by: str = "user"


class JobSubmitResponse(BaseModel):
    """Response from POST /studies/{id}/jobs."""
    batch_id: str | None
    jobs: list[JobRecord]


class BatchProgress(BaseModel):
    """Aggregated progress for the batch progress bar."""
    batch_id: str
    total: int
    complete: int
    failed: int
    running: int
    queued: int
    started_at: datetime
    completed_at: datetime | None = None
