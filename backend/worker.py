"""Celery worker entrypoint.

  celery -A worker.celery_app worker --loglevel=info
"""

from __future__ import annotations

from celery import Celery

from config import get_settings


settings = get_settings()

celery_app = Celery(
    "tlf_studio",
    broker=settings.redis_url,
    backend=settings.redis_url,
)
celery_app.conf.task_serializer = "json"
celery_app.conf.result_serializer = "json"
celery_app.conf.accept_content = ["json"]
celery_app.conf.task_track_started = True
celery_app.conf.timezone = "UTC"

# Register task modules
celery_app.autodiscover_tasks(["tasks"], force=True)
import tasks.generation  # noqa: E402,F401  ensure registration
