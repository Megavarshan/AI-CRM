"""
Celery application instance for the CRM service.

Workers are started with:
    celery -A celery_app worker --loglevel=info --queues=crm
"""

from celery import Celery

from config import settings

app = Celery(
    "crm",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "tasks.score_customers",
        "tasks.campaigns",
    ],
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
    task_default_queue="crm",
    task_routes={
        "tasks.score_customers.*": {"queue": "crm"},
    },
    # Nightly batch scoring at 02:00 UTC
    beat_schedule={
        "batch-score-all-customers-nightly": {
            "task": "tasks.score_customers.batch_score_all_customers",
            "schedule": 86400,  # every 24 h (use crontab in production)
        },
    },
)
