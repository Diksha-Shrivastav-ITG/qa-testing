from __future__ import annotations

from celery import Celery

from app.config import settings

celery_app = Celery(
    "shopify_qa",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    worker_concurrency=settings.max_concurrent_runs,
    task_track_started=True,
    broker_connection_timeout=4,
    broker_connection_retry_on_startup=False,
)
