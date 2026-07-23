import logging
import os
from datetime import UTC, datetime

from app.celery_app import celery_app
from app.adapters.provider_errors import ProviderInvocationError
from app.db import SessionLocal
from app.execution.ingest import run_ingest, run_reindex
from app.execution.assistant_attachments import purge_expired_assistant_attachments
from app.execution.memory import index_memory_records, run_compile_bid_wiki
from app.execution.memory_graph import run_extract_memory_graph
from app.execution.model_usage import finalize_workflow_model_reservation_failure
from app.execution.task_outbox import (
    claim_workflow_task_delivery,
    complete_workflow_task_delivery,
    dispatch_task_outbox_event,
    fail_workflow_task_delivery,
    recover_pending_task_outbox_events,
)
from app.models import ExecutionRun
from app.runtime.events import (
    RuntimeCancellationRequested,
    cancel_runtime_run,
    complete_runtime_run,
    fail_runtime_run,
    find_runtime_run_id,
    is_runtime_cancellation_requested,
    publish_node_failed,
    publish_node_started,
    publish_node_succeeded,
)

logger = logging.getLogger(__name__)

# Feature flag: product drafting uses the LangGraph graph by default.
# Set USE_LANGGRAPH=0/false/no only for explicit legacy single-shot drafting.
_USE_LANGGRAPH = os.getenv("USE_LANGGRAPH", "1").lower() in ("1", "true", "yes")


@celery_app.task(name="worker.ping")
def ping() -> str:
    return "pong"


@celery_app.task(name="worker.ingest_bundle")
def ingest_bundle(bundle_id: str) -> dict[str, str]:
    """Ingest a bundle: parse documents, extract chunks, update status."""
    return run_ingest(bundle_id)


@celery_app.task(name="worker.reindex_bundle")
def reindex_bundle(bundle_id: str) -> dict[str, str]:
    """Refresh bundle embeddings without reparsing source documents."""
    return run_reindex(bundle_id)


@celery_app.task(name="worker.compile_bid_wiki")
def compile_bid_wiki(compilation_run_id: str) -> dict[str, str]:
    """Create reviewable, source-backed Bid Wiki proposals from parsed materials."""
    return run_compile_bid_wiki(compilation_run_id)


@celery_app.task(name="worker.index_memory_records")
def index_memory(memory_record_ids: list[str]) -> dict[str, str]:
    """Refresh semantic vectors for active governed-memory records."""
    return index_memory_records(memory_record_ids)


def _execute_memory_graph_extraction(
    run_id: str,
    project_id: str,
    memory_record_id: str,
    *,
    provider_config_id: str | None = None,
    reasoning_effort: str | None = None,
    runtime_run_id: str | None = None,
) -> dict[str, str]:
    effective_runtime_run_id = runtime_run_id or find_runtime_run_id(run_id)
    node_name = "memory_graph_extraction"
    if is_runtime_cancellation_requested(effective_runtime_run_id):
        return _cancel_workflow(run_id, node_name, effective_runtime_run_id)
    publish_node_started(effective_runtime_run_id, node_name)
    try:
        result = run_extract_memory_graph(
            run_id,
            project_id,
            memory_record_id,
            provider_config_id=provider_config_id,
            reasoning_effort=reasoning_effort,
        )
    except ProviderInvocationError as exc:
        finalize_workflow_model_reservation_failure(run_id=run_id, error_code=exc.error_code)
        publish_node_failed(effective_runtime_run_id, node_name, exc.public_message, error_code=exc.error_code)
        _set_execution_status(run_id, "failed", error=exc.public_message)
        fail_runtime_run(effective_runtime_run_id, exc.public_message, error_code=exc.error_code)
        raise
    except Exception:
        finalize_workflow_model_reservation_failure(run_id=run_id, error_code="memory_graph_task_exception")
        logger.exception("Memory graph extraction failed", extra={"execution_run_id": run_id})
        public_message = "实体关系提案生成遇到内部错误，请稍后重试。"
        publish_node_failed(effective_runtime_run_id, node_name, public_message, error_code="memory_graph_task_exception")
        _set_execution_status(run_id, "failed", error=public_message)
        fail_runtime_run(effective_runtime_run_id, public_message, error_code="memory_graph_task_exception")
        raise
    if is_runtime_cancellation_requested(effective_runtime_run_id):
        return _cancel_workflow(run_id, node_name, effective_runtime_run_id)

    entity_count = result.get("entity_count", "0")
    relation_count = result.get("relation_count", "0")
    summary = "已生成待审核的实体关系提案。"
    if result.get("reused") == "true":
        summary = "已复用当前待审核的实体关系提案。"
    publish_node_succeeded(
        effective_runtime_run_id,
        node_name,
        summary,
        {"entity_count": entity_count, "relation_count": relation_count, "reused": result.get("reused") == "true"},
    )
    complete_runtime_run(
        effective_runtime_run_id,
        result={
            "execution_run_id": run_id,
            "proposal_memory_id": result.get("proposal_memory_id"),
            "entity_count": entity_count,
            "relation_count": relation_count,
            "reused": result.get("reused") == "true",
        },
    )
    return result


@celery_app.task(name="worker.extract_memory_graph")
def extract_memory_graph_task(
    run_id: str,
    project_id: str,
    memory_record_id: str,
    provider_config_id: str | None = None,
    reasoning_effort: str | None = None,
    runtime_run_id: str | None = None,
    outbox_event_id: str | None = None,
) -> dict[str, str]:
    """Run one durable graph-proposal delivery, ignoring active duplicates."""
    if not claim_workflow_task_delivery(outbox_event_id):
        logger.info("Ignoring duplicate memory graph delivery: event=%s", outbox_event_id)
        return {"status": "duplicate", "run_id": run_id}
    try:
        result = _execute_memory_graph_extraction(
            run_id,
            project_id,
            memory_record_id,
            provider_config_id=provider_config_id,
            reasoning_effort=reasoning_effort,
            runtime_run_id=runtime_run_id,
        )
    except ProviderInvocationError as exc:
        _fail_outbox_delivery_safely(outbox_event_id, exc.error_code)
        raise
    except Exception:
        _fail_outbox_delivery_safely(outbox_event_id, "memory_graph_task_exception")
        raise
    try:
        complete_workflow_task_delivery(outbox_event_id)
    except Exception:
        logger.exception("Memory graph task outbox completion failed: event=%s", outbox_event_id)
        raise
    return result


@celery_app.task(name="worker.cleanup_assistant_attachments")
def cleanup_assistant_attachments() -> dict[str, str]:
    """Enforce retention for private attachment staging objects."""
    return purge_expired_assistant_attachments()


def _execute_draft_section(
    run_id: str,
    project_id: str,
    section_key: str,
    review_feedback: str | None = None,
    provider_config_id: str | None = None,
    reasoning_effort: str | None = None,
    runtime_run_id: str | None = None,
) -> dict[str, str]:
    """Draft a section: retrieve evidence, call LLM, write section version.

    When ``USE_LANGGRAPH`` is enabled the task delegates to the compiled
    LangGraph agent graph (``app.graph.builder.invoke_graph``).  Otherwise
    it falls back to the legacy ``run_draft()`` helper.
    """
    effective_runtime_run_id = runtime_run_id or find_runtime_run_id(run_id)
    if is_runtime_cancellation_requested(effective_runtime_run_id):
        return _cancel_workflow(run_id, section_key, effective_runtime_run_id)

    if _USE_LANGGRAPH:
        from app.graph.builder import invoke_graph

        logger.info(
            "draft_section via LangGraph: run=%s project=%s section=%s",
            run_id,
            project_id,
            section_key,
        )
        try:
            result = invoke_graph(
                project_id=project_id,
                section_key=section_key,
                run_id=run_id,
                provider_config_id=provider_config_id,
                reasoning_effort=reasoning_effort,
                review_feedback=review_feedback,
                runtime_run_id=effective_runtime_run_id,
            )
        except RuntimeCancellationRequested:
            return _cancel_workflow(run_id, section_key, effective_runtime_run_id)
        except ProviderInvocationError as exc:
            finalize_workflow_model_reservation_failure(run_id=run_id, error_code=exc.error_code)
            _set_execution_status(run_id, "failed", error=exc.public_message)
            fail_runtime_run(
                effective_runtime_run_id,
                exc.public_message,
                error_code=exc.error_code,
            )
            raise
        except Exception:
            finalize_workflow_model_reservation_failure(run_id=run_id, error_code="workflow_graph_exception")
            logger.exception("LangGraph drafting invocation failed", extra={"execution_run_id": run_id})
            public_message = "工作流遇到内部错误，请稍后重试。"
            _set_execution_status(run_id, "failed", error=public_message)
            fail_runtime_run(effective_runtime_run_id, public_message, error_code="workflow_graph_exception")
            raise

        if is_runtime_cancellation_requested(effective_runtime_run_id):
            return _cancel_workflow(run_id, section_key, effective_runtime_run_id)

        if result.get("__interrupt__"):
            _set_execution_status(run_id, "awaiting_human")
            return {
                "status": "awaiting_human",
                "run_id": run_id,
                "section_key": section_key,
            }

        # Normalise the graph state dict into the same return shape the
        # Celery task has always produced so downstream callers keep working.
        if result.get("error"):
            finalize_workflow_model_reservation_failure(
                run_id=run_id,
                error_code=str(result.get("provider_error_code") or "workflow_graph_failed"),
            )
            _set_execution_status(run_id, "failed", error=str(result["error"]))
            fail_runtime_run(
                effective_runtime_run_id,
                str(result["error"]),
                error_code=str(result.get("provider_error_code") or "workflow_graph_failed"),
            )
            return {
                "status": "error",
                "run_id": run_id,
                "section_key": section_key,
                "error": result["error"],
            }

        if not result.get("persisted"):
            finalize_workflow_model_reservation_failure(
                run_id=run_id,
                error_code="workflow_not_persisted",
            )
            message = "工作流结束时未保存章节结果。"
            _set_execution_status(run_id, "failed", error=message)
            fail_runtime_run(effective_runtime_run_id, message, error_code="workflow_not_persisted")
            return {"status": "error", "run_id": run_id, "section_key": section_key, "error": message}

        complete_runtime_run(
            effective_runtime_run_id,
            result={
                "execution_run_id": run_id,
                "section_version_id": result.get("section_version_id"),
                "section_key": section_key,
            },
        )
        return {
            "status": "ok",
            "run_id": run_id,
            "section_key": section_key,
            "section_version_id": result.get("section_version_id", ""),
            "persisted": str(result.get("persisted", False)),
        }

    # Legacy path
    from app.execution.drafting import run_draft

    try:
        result = run_draft(
            run_id,
            project_id,
            section_key,
            review_feedback=review_feedback,
            provider_config_id=provider_config_id,
            reasoning_effort=reasoning_effort,
        )
    except RuntimeCancellationRequested:
        return _cancel_workflow(run_id, section_key, effective_runtime_run_id)
    except ProviderInvocationError as exc:
        finalize_workflow_model_reservation_failure(run_id=run_id, error_code=exc.error_code)
        _set_execution_status(run_id, "failed", error=exc.public_message)
        fail_runtime_run(
            effective_runtime_run_id,
            exc.public_message,
            error_code=exc.error_code,
        )
        raise
    except Exception:
        finalize_workflow_model_reservation_failure(run_id=run_id, error_code="legacy_workflow_exception")
        logger.exception("Legacy drafting invocation failed", extra={"execution_run_id": run_id})
        public_message = "工作流遇到内部错误，请稍后重试。"
        _set_execution_status(run_id, "failed", error=public_message)
        fail_runtime_run(effective_runtime_run_id, public_message, error_code="legacy_workflow_exception")
        raise
    if is_runtime_cancellation_requested(effective_runtime_run_id):
        return _cancel_workflow(run_id, section_key, effective_runtime_run_id)
    if result.get("status") == "succeeded":
        complete_runtime_run(effective_runtime_run_id, result={"execution_run_id": run_id, "section_key": section_key})
    else:
        fail_runtime_run(
            effective_runtime_run_id,
            str(result.get("error") or "章节起草失败。"),
            error_code="legacy_workflow_failed",
        )
    return result


@celery_app.task(name="worker.draft_section")
def draft_section(
    run_id: str,
    project_id: str,
    section_key: str,
    review_feedback: str | None = None,
    provider_config_id: str | None = None,
    reasoning_effort: str | None = None,
    runtime_run_id: str | None = None,
    outbox_event_id: str | None = None,
) -> dict[str, str]:
    """Execute one durable workflow delivery, ignoring active duplicate messages."""
    if not claim_workflow_task_delivery(outbox_event_id):
        logger.info("Ignoring duplicate workflow task delivery: event=%s", outbox_event_id)
        return {"status": "duplicate", "run_id": run_id, "section_key": section_key}
    try:
        result = _execute_draft_section(
            run_id,
            project_id,
            section_key,
            review_feedback=review_feedback,
            provider_config_id=provider_config_id,
            reasoning_effort=reasoning_effort,
            runtime_run_id=runtime_run_id,
        )
    except ProviderInvocationError as exc:
        _fail_outbox_delivery_safely(outbox_event_id, exc.error_code)
        raise
    except Exception:
        _fail_outbox_delivery_safely(outbox_event_id, "workflow_task_exception")
        raise
    try:
        complete_workflow_task_delivery(outbox_event_id)
    except Exception:
        # Let Celery preserve retry/loss semantics if the durable completion
        # marker cannot be recorded after work has finished.
        logger.exception("Task outbox completion failed: event=%s", outbox_event_id)
        raise
    return result


def _fail_outbox_delivery_safely(event_id: str | None, error_code: str) -> None:
    """Best-effort terminal marker that must not hide the workflow exception."""
    try:
        fail_workflow_task_delivery(event_id, error_code)
    except Exception:
        logger.exception("Task outbox failure marker failed: event=%s", event_id)


@celery_app.task(name="worker.dispatch_task_outbox_event")
def dispatch_task_outbox_event_task(event_id: str) -> dict[str, str]:
    """Publish one durable workflow task intent after its API transaction commits."""
    return dispatch_task_outbox_event(event_id)


@celery_app.task(name="worker.recover_task_outbox_events")
def recover_task_outbox_events() -> dict[str, str]:
    """Worker Beat recovery for pending or expired workflow task leases."""
    return recover_pending_task_outbox_events()


def _execute_resume_draft(
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
        runtime_run_id = find_runtime_run_id(run_id)
        if is_runtime_cancellation_requested(runtime_run_id):
            return _cancel_workflow(run_id, "", runtime_run_id)
        try:
            result = resume_graph(
                run_id=run_id,
                decision=decision,
                feedback=feedback,
            )
        except RuntimeCancellationRequested:
            return _cancel_workflow(run_id, "", runtime_run_id)
        except ProviderInvocationError as exc:
            finalize_workflow_model_reservation_failure(run_id=run_id, error_code=exc.error_code)
            _set_execution_status(run_id, "failed", error=exc.public_message)
            fail_runtime_run(runtime_run_id, exc.public_message, error_code=exc.error_code)
            raise
        except Exception:
            finalize_workflow_model_reservation_failure(run_id=run_id, error_code="workflow_resume_exception")
            logger.exception("LangGraph drafting resume failed", extra={"execution_run_id": run_id})
            public_message = "工作流恢复时遇到内部错误，请稍后重试。"
            _set_execution_status(run_id, "failed", error=public_message)
            fail_runtime_run(runtime_run_id, public_message, error_code="workflow_resume_exception")
            raise

        if is_runtime_cancellation_requested(runtime_run_id):
            return _cancel_workflow(run_id, "", runtime_run_id)

        if result.get("__interrupt__"):
            _set_execution_status(run_id, "awaiting_human")
            return {"status": "awaiting_human", "run_id": run_id}

        if result.get("error"):
            finalize_workflow_model_reservation_failure(
                run_id=run_id,
                error_code=str(result.get("provider_error_code") or "workflow_resume_failed"),
            )
            _set_execution_status(run_id, "failed", error=str(result["error"]))
            fail_runtime_run(
                runtime_run_id,
                str(result["error"]),
                error_code=str(result.get("provider_error_code") or "workflow_resume_failed"),
            )
            return {
                "status": "error",
                "run_id": run_id,
                "error": result["error"],
            }

        if not result.get("persisted"):
            finalize_workflow_model_reservation_failure(
                run_id=run_id,
                error_code="workflow_resume_not_persisted",
            )
            message = "恢复后的工作流未保存章节结果。"
            _set_execution_status(run_id, "failed", error=message)
            fail_runtime_run(runtime_run_id, message, error_code="workflow_resume_not_persisted")
            return {"status": "error", "run_id": run_id, "error": message}

        complete_runtime_run(
            runtime_run_id,
            result={
                "execution_run_id": run_id,
                "section_version_id": result.get("section_version_id"),
                "section_key": result.get("section_key"),
            },
        )
        return {
            "status": "ok",
            "run_id": run_id,
            "section_key": result.get("section_key", ""),
            "section_version_id": result.get("section_version_id", ""),
            "persisted": str(result.get("persisted", False)),
        }

    logger.warning("resume_draft called but USE_LANGGRAPH is disabled")
    return {"status": "error", "run_id": run_id, "error": "LANGGRAPH not enabled"}


@celery_app.task(name="worker.resume_draft")
def resume_draft(
    run_id: str,
    decision: str,
    feedback: str | None = None,
    outbox_event_id: str | None = None,
) -> dict[str, str]:
    """Execute a durable human-approval resume delivery exactly once per lease."""
    if not claim_workflow_task_delivery(outbox_event_id):
        logger.info("Ignoring duplicate workflow resume delivery: event=%s", outbox_event_id)
        return {"status": "duplicate", "run_id": run_id}
    try:
        result = _execute_resume_draft(run_id, decision, feedback)
    except ProviderInvocationError as exc:
        _fail_outbox_delivery_safely(outbox_event_id, exc.error_code)
        raise
    except Exception:
        _fail_outbox_delivery_safely(outbox_event_id, "workflow_resume_task_exception")
        raise
    try:
        complete_workflow_task_delivery(outbox_event_id)
    except Exception:
        logger.exception("Task outbox resume completion failed: event=%s", outbox_event_id)
        raise
    return result


def _set_execution_status(run_id: str, status: str, *, error: str | None = None) -> None:
    """Persist a terminal/pause status when a graph exits outside persist_result."""
    db = SessionLocal()
    try:
        run = db.get(ExecutionRun, run_id)
        if run is None:
            return
        run.status = status
        if status in {"succeeded", "failed", "cancelled", "error"}:
            run.finished_at = datetime.now(UTC)
        if error:
            run.output_json = {**(run.output_json or {}), "error": error}
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Failed to update execution run status", extra={"run_id": run_id})
        raise
    finally:
        db.close()


def _cancel_workflow(
    run_id: str,
    section_key: str,
    runtime_run_id: str | None,
) -> dict[str, str]:
    _set_execution_status(run_id, "cancelled")
    cancel_runtime_run(runtime_run_id)
    return {"status": "cancelled", "run_id": run_id, "section_key": section_key}


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
