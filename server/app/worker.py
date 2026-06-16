from celery import Celery
from celery.schedules import crontab
from app.core.config import settings

# Initialize Celery app
celery_app = Celery(
    "worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

# Configure Celery options
celery_app.conf.update(
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
)

# Configure periodic task schedules using Celery Beat
celery_app.conf.beat_schedule = {
    "cleanup-unverified-users-hourly": {
        "task": "app.tasks.cleanup_unverified_users",
        # Runs at the start of every hour
        "schedule": crontab(minute=0, hour="*/1"),
    },
}

# Auto-discover tasks in tasks.py within app package
celery_app.autodiscover_tasks(["app"])
