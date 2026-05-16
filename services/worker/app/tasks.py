from app.celery_app import celery_app
from app.execution.drafting import run_draft
from app.execution.ingest import run_ingest


@celery_app.task(name="worker.ping")
def ping() -> str:
    return "pong"


@celery_app.task(name="worker.ingest_bundle")
def ingest_bundle(bundle_id: str) -> dict[str, str]:
    """Ingest a bundle: parse documents, extract chunks, update status."""
    return run_ingest(bundle_id)


@celery_app.task(name="worker.draft_section")
def draft_section(run_id: str, project_id: str, section_key: str, review_feedback: str | None = None) -> dict[str, str]:
    """Draft a section: retrieve evidence, call LLM, write section version."""
    return run_draft(run_id, project_id, section_key, review_feedback=review_feedback)


@celery_app.task(name="worker.record_dead_letter", queue="dead_letter")
def record_dead_letter(task_id: str, task_name: str, error: str, args: list, kwargs: dict) -> dict[str, str]:
    """Record a failed task in the dead-letter queue for later inspection."""
    import logging
    logger = logging.getLogger(__name__)
    logger.error("Dead-letter: task_id=%s name=%s error=%s", task_id, task_name, error)
    return {"task_id": task_id, "task_name": task_name, "error": error, "status": "dead_letter"}


@celery_app.task(name="worker.backup_database")
def backup_database() -> dict:
    """Scheduled backup task for PostgreSQL database via pg_dump."""
    import logging
    import subprocess
    logger = logging.getLogger(__name__)
    try:
        result = subprocess.run(
            ["python", "scripts/backup.py", "backup"],
            capture_output=True, text=True, timeout=300,
        )
        if result.returncode == 0:
            logger.info("Scheduled backup completed successfully")
            return {"status": "ok", "output": result.stdout[:500]}
        else:
            logger.error("Scheduled backup failed: %s", result.stderr)
            return {"status": "error", "output": result.stderr[:500]}
    except Exception as exc:
        logger.exception("Scheduled backup exception")
        return {"status": "error", "detail": str(exc)[:500]}
