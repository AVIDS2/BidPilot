import os

from celery import Celery
from celery.schedules import crontab

REDIS_URL = os.environ.get("DOCPILOT_REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "docpilot-worker",
    broker=REDIS_URL,
    backend=REDIS_URL,
)


def _record_dead_letter(task, exc, task_id, args, kwargs, einfo) -> None:
    """Named failure hook so Windows spawn workers can pickle Celery config."""
    task.app.send_task(
        "worker.record_dead_letter",
        args=[task_id, task.name, str(exc), args, kwargs],
        queue="dead_letter",
    )


celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    # Retry and error handling
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_default_retry_delay=60,  # 1 minute between retries
    task_default_max_retries=3,
    # Dead-letter queue: failed tasks go to 'dead_letter' queue
    task_queues={
        "celery": {},
        "dead_letter": {},
    },
    task_default_queue="celery",
    # On failure, route to dead_letter queue
    task_on_failure=_record_dead_letter,
)

celery_app.conf.beat_schedule = {
    "recover-agent-wakes-every-10-seconds": {
        "task": "worker.recover_agent_wakes",
        "schedule": 10.0,
    },
    "deliver-business-webhooks-every-30-seconds": {
        "task": "worker.deliver_due_webhooks",
        "schedule": 30.0,
    },
    "poll-tender-radar-sources-minutely": {
        "task": "worker.poll_due_notice_sources",
        "schedule": crontab(minute="*"),
    },
    "recover-workflow-task-outbox-minutely": {
        "task": "worker.recover_task_outbox_events",
        "schedule": crontab(minute="*"),
    },
    "reconcile-runtime-runs-minutely": {
        "task": "worker.reconcile_runtime_runs",
        "schedule": crontab(minute="*"),
    },
    "cleanup-assistant-attachments-hourly": {
        "task": "worker.cleanup_assistant_attachments",
        "schedule": crontab(minute=17),
    },
    "backup-daily": {
        "task": "worker.backup_database",
        "schedule": crontab(hour=3, minute=0),
    },
}
celery_app.conf.timezone = "Asia/Shanghai"

celery_app.autodiscover_tasks(["app.tasks"], force=True)
