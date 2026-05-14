"""Celery task wrappers around generation_service."""

from __future__ import annotations

from worker import celery_app
from services import generation_service


@celery_app.task(name="tlf.generate_one")
def generate_one(study_id: str, job_id: str) -> dict[str, str]:
    """Run a single table generation. Returns the final job record dict."""
    record = generation_service.run_inline(study_id, job_id)
    return record.model_dump(mode="json")
