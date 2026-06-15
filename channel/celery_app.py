"""
Celery application instance for the Channel service.

Workers are started with:
    celery -A celery_app worker --loglevel=info --queues=channel
"""

from celery import Celery

from config import settings

app = Celery(
    "channel",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["tasks.deliver"],
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Eager mode runs tasks synchronously in-process (no Redis broker needed).
    task_always_eager=settings.CELERY_TASK_ALWAYS_EAGER,
    task_eager_propagates=True,
    task_default_queue="channel",
    task_routes={
        "tasks.deliver.*": {"queue": "channel"},
    },
)
