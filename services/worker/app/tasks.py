import logging
import os

from app.celery_app import celery_app
from app.execution.ingest import run_ingest

logger = logging.getLogger(__name__)

# Feature flag: set USE_LANGGRAPH=1 (or true/yes) to route drafting through
# the LangGraph agent graph instead of the legacy run_draft() path.
_USE_LANGGRAPH = os.getenv("USE_LANGGRAPH", "0").lower() in ("1", "true", "yes")


@celery_app.task(name="worker.ping")
def ping() -> str:
    return "pong"


@celery_app.task(name="worker.ingest_bundle")
def ingest_bundle(bundle_id: str) -> dict[str, str]:
    """Ingest a bundle: parse documents, extract chunks, update status."""
    return run_ingest(bundle_id)


@celery_app.task(name="worker.draft_section")
def draft_section(
    run_id: str,
    project_id: str,
    section_key: str,
    review_feedback: str | None = None,
    provider_config_id: str | None = None,
) -> dict[str, str]:
    """Draft a section: retrieve evidence, call LLM, write section version.

    When ``USE_LANGGRAPH`` is enabled the task delegates to the compiled
    LangGraph agent graph (``app.graph.builder.invoke_graph``).  Otherwise
    it falls back to the legacy ``run_draft()`` helper.
    """
    if _USE_LANGGRAPH:
        from app.graph.builder import invoke_graph

        logger.info(
            "draft_section via LangGraph: run=%s project=%s section=%s",
            run_id,
            project_id,
            section_key,
        )
        result = invoke_graph(
            project_id=project_id,
            section_key=section_key,
            run_id=run_id,
            provider_config_id=provider_config_id,
            review_feedback=review_feedback,
        )

        # Normalise the graph state dict into the same return shape the
        # Celery task has always produced so downstream callers keep working.
        if result.get("error"):
            return {
                "status": "error",
                "run_id": run_id,
                "section_key": section_key,
                "error": result["error"],
            }

        return {
            "status": "ok",
            "run_id": run_id,
            "section_key": section_key,
            "section_version_id": result.get("section_version_id", ""),
            "persisted": str(result.get("persisted", False)),
        }

    # Legacy path
    from app.execution.drafting import run_draft

    return run_draft(
        run_id,
        project_id,
        section_key,
        review_feedback=review_feedback,
        provider_config_id=provider_config_id,
    )


@celery_app.task(name="worker.resume_draft")
def resume_draft(
    run_id: str,
    decision: str,
    feedback: str | None = None,
) -> dict[str, str]:
    """Resume an interrupted LangGraph drafting run after human approval.

    Called by the API when a human reviewer submits their decision via the
    ``POST /drafting/runs/{run_id}/resume`` endpoint.

    Args:
        run_id: UUID of the ExecutionRun to resume.
        decision: "approved" or "rejected_with_feedback".
        feedback: Optional human feedback when rejecting.
    """
    if _USE_LANGGRAPH:
        from app.graph.builder import resume_graph

        logger.info(
            "resume_draft via LangGraph: run=%s decision=%s",
            run_id,
            decision,
        )
        result = resume_graph(
            run_id=run_id,
            decision=decision,
            feedback=feedback,
        )

        if result.get("error"):
            return {
                "status": "error",
                "run_id": run_id,
                "error": result["error"],
            }

        return {
            "status": "ok",
            "run_id": run_id,
            "section_key": result.get("section_key", ""),
            "section_version_id": result.get("section_version_id", ""),
            "persisted": str(result.get("persisted", False)),
        }

    logger.warning("resume_draft called but USE_LANGGRAPH is disabled")
    return {"status": "error", "run_id": run_id, "error": "LANGGRAPH not enabled"}


@celery_app.task(name="worker.record_dead_letter", queue="dead_letter")
def record_dead_letter(task_id: str, task_name: str, error: str, args: list, kwargs: dict) -> dict[str, str]:
    """Record a failed task in the dead-letter queue for later inspection."""
    logger.error("Dead-letter: task_id=%s name=%s error=%s", task_id, task_name, error)
    return {"task_id": task_id, "task_name": task_name, "error": error, "status": "dead_letter"}


@celery_app.task(name="worker.backup_database")
def backup_database() -> dict:
    """Scheduled backup task for PostgreSQL database via pg_dump."""
    import subprocess

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
