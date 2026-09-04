import logging
import os
import asyncio
import json
import httpx
from celery.exceptions import Retry
from datetime import UTC, datetime
from urllib.parse import parse_qs, urlparse

from sqlalchemy import select

from app.celery_app import celery_app
from app.adapters.provider_errors import ProviderInvocationError
from app.db import SessionLocal
from app.execution.ingest import run_ingest, run_reindex
from app.execution.ingest import bundle_has_retryable_embedding_failure, mark_bundle_index_retrying
from app.execution.assistant_attachments import purge_expired_assistant_attachments
from app.execution.memory import index_memory_records, run_compile_bid_wiki
from app.execution.memory_graph import run_extract_memory_graph
from app.execution.mem0_profile import capture_mem0_profile_for_run, delete_mem0_profile_for_user
from app.execution.model_usage import finalize_workflow_model_reservation_failure
from app.execution.review_resume import resolve_durable_review_resume
from app.radar.service import poll_due_notice_sources
from app.webhooks.service import deliver_due_webhook_deliveries
from app.execution.task_outbox import (
    claim_workflow_task_delivery,
    complete_workflow_task_delivery,
    dispatch_task_outbox_event,
    fail_workflow_task_delivery,
    recover_pending_task_outbox_events,
    retry_workflow_task_delivery,
)
from app.models import ExecutionRun
from app.models import Bundle, Notification, RuntimeRun, User
from app.auth.schemas import CurrentUser
from app.documents.web_import import download_remote_artifact_to_tempfile
from app.documents.service import upload_artifact_file_command, upload_document_command
from app.runtime.events import publish_runtime_event
from app.documents.import_errors import RemoteImportError
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
from contracts.document_ingestion import MAX_SOURCE_DOCUMENT_BYTES, canonical_source_document_mime_type, source_document_is_parseable
from contracts.pi_runtime import pi_model_api, pi_model_provider, pi_thinking_level
from contracts.pi_bridge import encode_agent_wake_token, encode_assistant_task_token, encode_pi_bridge_token
from contracts.runtime import RuntimeEventType, RuntimeRunStatus

logger = logging.getLogger(__name__)

# Feature flag: product drafting uses the LangGraph graph by default.
# Set USE_LANGGRAPH=0/false/no only for explicit legacy single-shot drafting.
_USE_LANGGRAPH = os.getenv("USE_LANGGRAPH", "1").lower() in ("1", "true", "yes")
_INDEX_RETRY_MAX_ATTEMPTS = 3
_INDEX_RETRY_BASE_DELAY_SECONDS = 5
_ASSISTANT_TASK_MAX_RETRIES = 8


def _fail_assistant_task_after_retries(
    runtime_run_id: str,
    outbox_event_id: str | None,
    *,
    error_code: str,
    message: str,
) -> dict[str, object]:
    """Make transport exhaustion terminal instead of leaving a run running forever."""
    try:
        fail_runtime_run(runtime_run_id, message, error_code=error_code)
    except Exception:  # noqa: BLE001 - preserve the original task failure
        logger.exception("Assistant runtime failure reconciliation failed", extra={"runtime_run_id": runtime_run_id})
    fail_workflow_task_delivery(outbox_event_id, error_code)
    return {"status": "failed", "runtime_run_id": runtime_run_id}


def _retry_transient_bundle_index(task, bundle_id: str) -> bool:
    """Schedule a bounded retry only for a durable transient index outcome."""
    if not bundle_has_retryable_embedding_failure(bundle_id):
        return False
    retry_count = int(getattr(task.request, "retries", 0) or 0)
    if retry_count >= _INDEX_RETRY_MAX_ATTEMPTS:
        return False
    mark_bundle_index_retrying(bundle_id)
    delay = _INDEX_RETRY_BASE_DELAY_SECONDS * (2**retry_count)
    task.retry(
        exc=RuntimeError("retryable embedding provider failure"),
        countdown=delay,
        max_retries=_INDEX_RETRY_MAX_ATTEMPTS,
    )
    return True


@celery_app.task(name="worker.ping")
def ping() -> str:
    return "pong"


def _wake_run_id(link: str | None) -> str | None:
    if not link:
        return None
    parsed = urlparse(link)
    if not parsed.path.startswith("/agent"):
        return None
    value = parse_qs(parsed.query).get("wake", [None])[0]
    return value if isinstance(value, str) and value else None


def _mark_wake_notifications_read(wake_run_id: str) -> None:
    """Close durable wake notices once the API has consumed or rejected them."""
    db = SessionLocal()
    try:
        notifications = list(
            db.scalars(
                select(Notification).where(
                    Notification.type == "agent_task",
                    Notification.read.is_(False),
                    Notification.link.contains(f"wake={wake_run_id}"),
                )
            )
        )
        for notification in notifications:
            notification.read = True
        if notifications:
            db.commit()
    except Exception:  # noqa: BLE001 - wake cleanup must not hide delivery results
        db.rollback()
        logger.exception("Failed to close consumed agent wake notification", extra={"wake_run_id": wake_run_id})
    finally:
        db.close()


@celery_app.task(name="worker.resume_agent_wake", bind=True, max_retries=5)
def resume_agent_wake(self, wake_run_id: str) -> dict[str, object]:
    """Deliver one durable completion observation to the parent Pi session."""
    secret = os.getenv("DOCPILOT_PI_INTERNAL_SECRET") or os.getenv("DOCPILOT_JWT_SECRET")
    if not secret:
        raise RuntimeError("Pi internal wake secret is not configured")
    token = encode_agent_wake_token(wake_run_id=wake_run_id, secret=secret)
    api_url = os.getenv("DOCPILOT_INTERNAL_API_URL", "http://api:8000").rstrip("/")
    try:
        response = httpx.post(
            f"{api_url}/internal/pi/wakes/resume",
            headers={"Authorization": f"Bearer {token}"},
            json={"wake_run_id": wake_run_id},
            timeout=httpx.Timeout(connect=10.0, read=900.0, write=30.0, pool=30.0),
        )
        response.raise_for_status()
        payload = response.json()
        _mark_wake_notifications_read(wake_run_id)
        return payload if isinstance(payload, dict) else {"status": "completed"}
    except (httpx.TimeoutException, httpx.RequestError, httpx.HTTPStatusError) as exc:
        status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
        if status is not None and status < 500:
            if status in {400, 403, 404}:
                _mark_wake_notifications_read(wake_run_id)
            return {"status": "rejected", "wake_run_id": wake_run_id, "http_status": status}
        raise self.retry(exc=exc, countdown=min(60, 2 ** int(self.request.retries)))


@celery_app.task(name="worker.recover_agent_wakes")
def recover_agent_wakes() -> dict[str, object]:
    """Redispatch unread wakes; the API idempotency key absorbs duplicates."""
    db = SessionLocal()
    try:
        notifications = list(
            db.scalars(
                select(Notification)
                .where(Notification.type == "agent_task", Notification.read.is_(False))
                .order_by(Notification.created_at.asc())
                .limit(50)
            )
        )
        wake_ids = [wake_id for item in notifications if (wake_id := _wake_run_id(item.link))]
    finally:
        db.close()
    for wake_id in dict.fromkeys(wake_ids):
        celery_app.send_task("worker.resume_agent_wake", args=[wake_id])
    return {"status": "dispatched", "count": len(set(wake_ids))}


@celery_app.task(name="worker.run_subagent", bind=True, max_retries=120)
def run_subagent(self, runtime_run_id: str, *, outbox_event_id: str | None = None) -> dict[str, object]:
    """Execute one durable Pi child through the governed sidecar."""
    db = SessionLocal()
    try:
        runtime_run = db.scalar(select(RuntimeRun).where(RuntimeRun.id == runtime_run_id))
        if runtime_run is None:
            if not claim_workflow_task_delivery(outbox_event_id):
                return {"status": "duplicate", "runtime_run_id": runtime_run_id}
            complete_workflow_task_delivery(outbox_event_id)
            return {"status": "missing", "runtime_run_id": runtime_run_id}
        subagent = (runtime_run.input_json or {}).get("subagent") or {}
        previous_id = subagent.get("previous_child_run_id")
        if previous_id:
            previous = db.scalar(select(RuntimeRun).where(RuntimeRun.id == previous_id))
            if previous is None:
                if not claim_workflow_task_delivery(outbox_event_id):
                    return {"status": "duplicate", "runtime_run_id": runtime_run_id}
                fail_runtime_run(runtime_run_id, "链式子 Agent 的前置步骤不存在。", error_code="subagent_dependency_missing")
                complete_workflow_task_delivery(outbox_event_id)
                return {"status": "failed", "runtime_run_id": runtime_run_id}
            if previous is not None and previous.status not in {"succeeded", "failed", "cancelled", "expired"}:
                # Do not claim the outbox lease until the dependency is terminal.
                # Celery owns this bounded wait; the model is not polled or charged.
                raise self.retry(countdown=5, max_retries=120)
        if not claim_workflow_task_delivery(outbox_event_id):
            return {"status": "duplicate", "runtime_run_id": runtime_run_id}
        if previous_id:
            if previous.status != "succeeded":
                fail_runtime_run(runtime_run_id, "链式子 Agent 的前置步骤未成功。", error_code="subagent_dependency_failed")
                complete_workflow_task_delivery(outbox_event_id)
                return {"status": "failed", "runtime_run_id": runtime_run_id}

        user_row = db.get(User, runtime_run.user_id)
        if user_row is None:
            fail_runtime_run(runtime_run_id, "子 Agent 所属用户不存在。", error_code="subagent_user_missing")
            complete_workflow_task_delivery(outbox_event_id)
            return {"status": "failed", "runtime_run_id": runtime_run_id}

        from app.runtime.model import resolve_agent_model
        from app.providers.service import get_provider_config
        from app.security.secrets import decrypt_secret

        user = CurrentUser(
            id=user_row.id,
            email=user_row.email,
            display_name=user_row.display_name,
            role=user_row.role,
            plan=user_row.subscription.plan if user_row.subscription is not None else "starter",
            email_verified=user_row.email_verified,
            disabled=user_row.disabled,
            org_id=user_row.org_id,
            org_slug=user_row.organization.slug if user_row.organization is not None else "",
        )
        config = get_provider_config(db, runtime_run.provider_config_id, user.id) if runtime_run.provider_config_id else None
        if config is not None:
            resolved = resolve_agent_model(
                provider_type=config.provider_type,
                provider_id=config.provider_id,
                api_key=decrypt_secret(config.api_key),
                base_url=config.api_url,
                model=runtime_run.model or config.model,
            )
        else:
            resolved = resolve_agent_model()
        profile = str(subagent.get("profile") or "general")
        prompt = str(subagent.get("prompt") or "").strip()
        pi_runtime = subagent.get("pi_runtime")
        if not isinstance(pi_runtime, dict) or pi_runtime.get("version") != "1":
            fail_runtime_run(runtime_run_id, "子 Agent 缺少受信任的执行契约。", error_code="subagent_runtime_contract_missing")
            complete_workflow_task_delivery(outbox_event_id)
            return {"status": "failed", "runtime_run_id": runtime_run_id}
        if previous_id and previous is not None:
            previous_summary = str((previous.result_json or {}).get("summary") or "").strip()[:4000]
            if previous_summary:
                if "{previous}" in prompt:
                    prompt = prompt.replace("{previous}", previous_summary)
                else:
                    prompt = f"{prompt}\n\nPrevious verified step result:\n{previous_summary}"
        system_prompt = (
            "You are a governed BidPilot child agent. Work only on the delegated task. "
            "Inspect tool observations, report uncertainty, and stop when the task is verified or blocked. "
            f"Specialist profile: {profile}."
        )
        callback_url = os.getenv("DOCPILOT_PI_TOOL_BRIDGE_URL", "http://api:8000/internal/pi/tools/execute")
        sidecar_url = os.getenv("DOCPILOT_PI_AGENT_URL", "http://pi-agent:8787").rstrip("/")
        bridge_secret = os.getenv("DOCPILOT_PI_INTERNAL_SECRET") or os.getenv("DOCPILOT_JWT_SECRET")
        if not bridge_secret:
            fail_runtime_run(runtime_run_id, "Pi 工具桥接密钥未配置。", error_code="pi_bridge_secret_missing")
            complete_workflow_task_delivery(outbox_event_id)
            return {"status": "failed", "runtime_run_id": runtime_run_id}
        runtime_run.status = RuntimeRunStatus.RUNNING.value
        runtime_run.started_at = runtime_run.started_at or datetime.now(UTC)
        db.commit()
        request = {
            "runId": runtime_run.id,
            "sessionId": f"bidpilot:subagent:{runtime_run.id}",
            "systemPrompt": system_prompt,
            "userMessage": prompt,
            "model": {
                "provider": pi_model_provider(resolved.provider_type, resolved.provider_id, resolved.base_url),
                "id": resolved.model,
                "name": resolved.model,
                "api": pi_model_api(resolved.provider_type, resolved.provider_id),
                "baseUrl": (resolved.base_url or "").rstrip("/"),
                "apiKey": resolved.api_key,
                "reasoning": runtime_run.reasoning_effort not in {None, "off"},
                "thinkingLevel": pi_thinking_level(runtime_run.reasoning_effort),
            },
            "tools": pi_runtime.get("tools") or [],
            "resources": pi_runtime.get("resources") or {},
            "sandbox": pi_runtime.get("sandbox") or {},
            "toolCallback": {
                "url": callback_url,
                "token": encode_pi_bridge_token(
                    run_id=runtime_run.id,
                    user_id=user.id,
                    org_id=user.org_id,
                    email=user.email,
                    display_name=user.display_name,
                    role=user.role,
                    plan=user.plan,
                    org_slug=user.org_slug,
                    secret=bridge_secret,
                ),
            },
            "maxTurns": int(subagent.get("max_steps") or 8),
        }
        publish_runtime_event(runtime_run_id, RuntimeEventType.CAPABILITY_STARTED, "子 Agent 已启动，正在执行委派任务。", {"capability": "subagent", "profile": profile})

        async def consume() -> tuple[str, str | None]:
            text_parts: list[str] = []
            terminal: str | None = None
            timeout = httpx.Timeout(connect=10.0, read=None, write=30.0, pool=30.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream(
                    "POST",
                    f"{sidecar_url}/v1/runs",
                    json=request,
                    headers={"Authorization": f"Bearer {bridge_secret}"},
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue
                        event = json.loads(line)
                        event_type = str(event.get("type") or "")
                        if event_type == "text.delta":
                            text_parts.append(str(event.get("delta") or ""))
                        elif event_type == "tool.started":
                            publish_runtime_event(
                                runtime_run_id,
                                RuntimeEventType.CAPABILITY_PROGRESSED,
                                f"子 Agent 正在调用 {event.get('name') or '工具'}。",
                                {
                                    "capability": "subagent",
                                    "phase": "tool_started",
                                    "tool": event.get("name"),
                                    "tool_call_id": event.get("tool_call_id"),
                                },
                            )
                        elif event_type == "tool.completed":
                            failed = bool(event.get("is_error"))
                            publish_runtime_event(
                                runtime_run_id,
                                RuntimeEventType.CAPABILITY_PROGRESSED,
                                (
                                    f"子 Agent 调用 {event.get('name') or '工具'} 失败。"
                                    if failed
                                    else f"子 Agent 已完成 {event.get('name') or '工具'}。"
                                ),
                                {
                                    "capability": "subagent",
                                    "phase": "tool_failed" if failed else "tool_completed",
                                    "tool": event.get("name"),
                                    "tool_call_id": event.get("tool_call_id"),
                                },
                            )
                        elif event_type == "agent.failed":
                            terminal = "failed"
                        elif event_type == "agent.completed":
                            terminal = "completed"
            return "".join(text_parts).strip(), terminal

        text, terminal = asyncio.run(consume())
        if terminal != "completed":
            fail_runtime_run(runtime_run_id, "子 Agent 未能安全完成。", error_code="subagent_stream_incomplete")
            complete_workflow_task_delivery(outbox_event_id)
            return {"status": "failed", "runtime_run_id": runtime_run_id}
        result = {"status": "succeeded", "runtime_run_id": runtime_run_id, "profile": profile, "summary": text[:4000]}
        publish_runtime_event(runtime_run_id, RuntimeEventType.CAPABILITY_SUCCEEDED, "子 Agent 已完成委派任务。", {"capability": "subagent", "profile": profile})
        complete_runtime_run(runtime_run_id, result=result)
        complete_workflow_task_delivery(outbox_event_id)
        return result
    except Retry:
        raise
    except Exception:
        logger.exception("Subagent execution failed", extra={"runtime_run_id": runtime_run_id})
        try:
            fail_runtime_run(runtime_run_id, "子 Agent 执行失败，请查看运行记录后重试。", error_code="subagent_execution_failed")
            fail_workflow_task_delivery(outbox_event_id, "subagent_execution_failed")
        except Exception:
            logger.exception("Subagent failure reconciliation failed", extra={"runtime_run_id": runtime_run_id})
        return {"status": "failed", "runtime_run_id": runtime_run_id}
    finally:
        db.close()


@celery_app.task(name="worker.run_assistant_turn", bind=True, max_retries=8)
def run_assistant_turn(self, runtime_run_id: str, *, outbox_event_id: str | None = None) -> dict[str, object]:
    """Drive one queued Pi assistant turn without a browser connection."""

    db = SessionLocal()
    try:
        runtime_run = db.scalar(select(RuntimeRun).where(RuntimeRun.id == runtime_run_id))
        if runtime_run is None:
            if claim_workflow_task_delivery(outbox_event_id):
                complete_workflow_task_delivery(outbox_event_id)
            return {"status": "missing", "runtime_run_id": runtime_run_id}
        if runtime_run.status in {"succeeded", "failed", "cancelled", "expired", "awaiting_approval", "awaiting_input"}:
            if claim_workflow_task_delivery(outbox_event_id):
                complete_workflow_task_delivery(outbox_event_id)
            return {"status": runtime_run.status, "runtime_run_id": runtime_run_id}
        if not claim_workflow_task_delivery(outbox_event_id):
            return {"status": "duplicate", "runtime_run_id": runtime_run_id}
        secret = os.getenv("DOCPILOT_PI_INTERNAL_SECRET") or os.getenv("DOCPILOT_JWT_SECRET")
        if not secret:
            fail_runtime_run(runtime_run_id, "执行服务配置不完整。", error_code="assistant_task_secret_missing")
            fail_workflow_task_delivery(outbox_event_id, "assistant_task_secret_missing")
            return {"status": "failed", "runtime_run_id": runtime_run_id}
        token = encode_assistant_task_token(
            run_id=runtime_run.id,
            user_id=runtime_run.user_id,
            org_id=runtime_run.org_id,
            secret=secret,
        )
        api_url = os.getenv("DOCPILOT_INTERNAL_API_URL", "http://api:8000").rstrip("/")
        try:
            response = httpx.post(
                f"{api_url}/internal/pi/runs/{runtime_run.id}/execute",
                headers={"Authorization": f"Bearer {token}"},
                timeout=httpx.Timeout(connect=10, read=900, write=30, pool=30),
            )
            if response.status_code == 409:
                if int(getattr(self.request, "retries", 0) or 0) >= _ASSISTANT_TASK_MAX_RETRIES:
                    return _fail_assistant_task_after_retries(
                        runtime_run_id,
                        outbox_event_id,
                        error_code="assistant_task_busy_exhausted",
                        message="助手运行长时间未能取得执行权，已安全停止。请重新发送。",
                    )
                retry_workflow_task_delivery(outbox_event_id, "assistant_task_busy", delay_seconds=15)
                raise self.retry(countdown=15, max_retries=_ASSISTANT_TASK_MAX_RETRIES)
            response.raise_for_status()
            result = response.json()
        except Retry:
            raise
        except httpx.HTTPStatusError as exc:
            if exc.response is not None and exc.response.status_code < 500:
                return _fail_assistant_task_after_retries(
                    runtime_run_id,
                    outbox_event_id,
                    error_code="assistant_task_rejected",
                    message="助手执行服务拒绝了本次运行，请稍后重试。",
                )
            if int(getattr(self.request, "retries", 0) or 0) >= _ASSISTANT_TASK_MAX_RETRIES:
                return _fail_assistant_task_after_retries(
                    runtime_run_id,
                    outbox_event_id,
                    error_code="assistant_task_transport_exhausted",
                    message="助手运行等待时间过长，已安全停止。请稍后重试。",
                )
            retry_workflow_task_delivery(outbox_event_id, "assistant_task_transport_retry")
            raise self.retry(exc=exc, countdown=min(120, 2 ** int(self.request.retries)), max_retries=_ASSISTANT_TASK_MAX_RETRIES)
        except (httpx.TimeoutException, httpx.RequestError) as exc:
            if int(getattr(self.request, "retries", 0) or 0) >= _ASSISTANT_TASK_MAX_RETRIES:
                return _fail_assistant_task_after_retries(
                    runtime_run_id,
                    outbox_event_id,
                    error_code="assistant_task_transport_exhausted",
                    message="助手运行等待时间过长，已安全停止。请稍后重试。",
                )
            retry_workflow_task_delivery(outbox_event_id, "assistant_task_transport_retry")
            raise self.retry(exc=exc, countdown=min(120, 2 ** int(self.request.retries)), max_retries=_ASSISTANT_TASK_MAX_RETRIES)
        try:
            capture_mem0_profile.delay(runtime_run_id)
        except Exception:  # noqa: BLE001 - optional profile capture is fail-open
            logger.warning("Could not enqueue Mem0 profile capture: run=%s", runtime_run_id, exc_info=True)
        complete_workflow_task_delivery(outbox_event_id)
        return result if isinstance(result, dict) else {"status": "completed", "runtime_run_id": runtime_run_id}
    except Retry:
        raise
    except Exception:
        logger.exception("Assistant task execution failed", extra={"runtime_run_id": runtime_run_id})
        _fail_assistant_task_after_retries(
            runtime_run_id,
            outbox_event_id,
            error_code="assistant_task_failed",
            message="助手执行服务发生异常，已安全停止。请稍后重试。",
        )
        raise
    finally:
        db.close()


@celery_app.task(name="worker.run_deep_research", bind=True, max_retries=3)
def run_deep_research(self, runtime_run_id: str, *, outbox_event_id: str | None = None) -> dict[str, object]:
    """Run one bounded Deep Research pipeline outside the Pi conversation."""
    from app.execution.deep_research import execute_deep_research

    try:
        return execute_deep_research(runtime_run_id, outbox_event_id=outbox_event_id)
    except Exception as exc:  # noqa: BLE001 - Celery retries transient worker errors
        logger.exception("Deep Research task failed: %s", runtime_run_id)
        if self.request.retries >= 2:
            raise
        raise self.retry(exc=exc, countdown=min(60, 10 * (self.request.retries + 1)))


@celery_app.task(name="worker.capture_mem0_profile", bind=True, max_retries=3)
def capture_mem0_profile(self, runtime_run_id: str) -> dict[str, object]:
    """Persist only low-risk profile signals through the official Mem0 SDK."""

    result = capture_mem0_profile_for_run(runtime_run_id)
    if result.get("status") == "failed" and int(getattr(self.request, "retries", 0) or 0) < 3:
        raise self.retry(countdown=min(120, 2 ** int(self.request.retries)))
    return result


@celery_app.task(name="worker.delete_mem0_profile", bind=True, max_retries=5)
def delete_mem0_profile(self, user_id: str, org_ids: list[str]) -> dict[str, object]:
    """Complete a scoped Mem0 deletion after a BidPilot account is removed."""

    result = delete_mem0_profile_for_user(user_id=user_id, org_ids=org_ids)
    if result.get("status") == "failed" and int(getattr(self.request, "retries", 0) or 0) < 5:
        raise self.retry(countdown=min(300, 2 ** int(self.request.retries)))
    return result


@celery_app.task(name="worker.import_remote_document", bind=True)
def import_remote_document(self, runtime_run_id: str) -> dict[str, object]:
    """Download one confirmed remote artifact and attach it to its bundle.

    The API returns before this task starts so large or slow public files do
    not hold an Agent SSE request open.  RuntimeRun is the durable job record;
    no URL is rewritten or retried with a different protocol here.
    """
    db = SessionLocal()
    try:
        runtime_run = db.scalar(select(RuntimeRun).where(RuntimeRun.id == runtime_run_id))
        if runtime_run is None:
            return {"status": "missing", "runtime_run_id": runtime_run_id}
        if runtime_run.status in {"succeeded", "failed", "cancelled", "expired"}:
            return {"status": runtime_run.status, "runtime_run_id": runtime_run_id}
        user_row = db.get(User, runtime_run.user_id)
        if user_row is None:
            fail_runtime_run(runtime_run_id, "导入任务所属用户不存在。", error_code="remote_import_user_missing")
            return {"status": "failed", "runtime_run_id": runtime_run_id}
        args = runtime_run.input_json or {}
        project_id = str(args.get("project_id") or "")
        bundle_id = str(args.get("bundle_id") or "")
        url = str(args.get("url") or "")
        filename = str(args.get("filename") or "").strip() or None
        if not project_id or not bundle_id or not url:
            fail_runtime_run(runtime_run_id, "远程导入任务缺少项目、资料包或地址。", error_code="remote_import_input_invalid")
            return {"status": "failed", "runtime_run_id": runtime_run_id}
        user = CurrentUser(
            id=user_row.id,
            email=user_row.email,
            display_name=user_row.display_name,
            role=user_row.role,
            email_verified=user_row.email_verified,
            disabled=user_row.disabled,
            org_id=user_row.org_id,
            org_slug=user_row.organization.slug if user_row.organization is not None else "",
        )
        publish_runtime_event(
            runtime_run_id,
            RuntimeEventType.CAPABILITY_STARTED,
            "正在下载已确认的远程资料。",
            {"capability": "fetch_url_to_project", "phase": "download"},
        )
        downloaded = download_remote_artifact_to_tempfile(url, filename=filename)
        try:
            publish_runtime_event(
                runtime_run_id,
                RuntimeEventType.CAPABILITY_PROGRESSED,
                "远程资料下载完成，正在写入项目资料包。",
                {"capability": "fetch_url_to_project", "phase": "storage", "bytes": downloaded.byte_count},
            )
            mime_type = canonical_source_document_mime_type(
                filename=downloaded.filename,
                content_type=downloaded.content_type,
            )
            if source_document_is_parseable(mime_type or ""):
                if downloaded.byte_count > MAX_SOURCE_DOCUMENT_BYTES:
                    raise RemoteImportError(
                        "remote_too_large",
                        "可解析的远程资料超过当前 25 MB 上限。请先压缩、拆分，或改为仅归档附件。",
                        retryable=False,
                    )
                with downloaded.file_path.open("rb") as source_file:
                    doc = upload_document_command(
                        db,
                        bundle_id=bundle_id,
                        filename=downloaded.filename,
                        content_type=downloaded.content_type,
                        data=source_file.read(),
                        current_user=user,
                        source_url=downloaded.source_url,
                    )
            else:
                doc = upload_artifact_file_command(
                    db,
                    bundle_id=bundle_id,
                    filename=downloaded.filename,
                    content_type=downloaded.content_type,
                    file_path=str(downloaded.file_path),
                    byte_count=downloaded.byte_count,
                    checksum=downloaded.checksum,
                    signature=downloaded.signature,
                    current_user=user,
                    source_url=downloaded.source_url,
                )
        finally:
            downloaded.cleanup()
        bundle = db.get(Bundle, bundle_id)
        result = {
            "status": "succeeded",
            "runtime_run_id": runtime_run_id,
            "project_id": project_id,
            "bundle_id": bundle_id,
            "bundle_label": bundle.label if bundle is not None else "项目资料包",
            "document_id": doc.id,
            "filename": doc.original_filename,
            "bytes": downloaded.byte_count,
            "source_url": downloaded.source_url,
            "import_mode": "artifact",
            "parse_status": doc.parse_status,
            "ingest_queued": doc.ingest_queued,
            "storage_status": "stored_no_parse" if doc.parse_status == "not_applicable" else "queued_for_ingestion",
        }
        publish_runtime_event(
            runtime_run_id,
            RuntimeEventType.CAPABILITY_SUCCEEDED,
            f"远程资料「{doc.original_filename}」已写入项目资料包。",
            {"capability": "fetch_url_to_project", "document_id": doc.id, "filename": doc.original_filename},
        )
        complete_runtime_run(runtime_run_id, result=result)
        return result
    except RemoteImportError as exc:
        fail_runtime_run(runtime_run_id, exc.public_message, error_code=exc.error_code)
        return {"status": "failed", "runtime_run_id": runtime_run_id, "error_code": exc.error_code}
    except Exception:
        logger.exception("Remote document import failed", extra={"runtime_run_id": runtime_run_id})
        fail_runtime_run(runtime_run_id, "远程资料下载或入库失败，请查看任务详情后重试。", error_code="remote_import_task_failed")
        return {"status": "failed", "runtime_run_id": runtime_run_id, "error_code": "remote_import_task_failed"}
    finally:
        db.close()


@celery_app.task(name="worker.ingest_bundle", bind=True)
def ingest_bundle(self, bundle_id: str) -> dict[str, str]:
    """Ingest a bundle: parse documents, extract chunks, update status."""
    result = run_ingest(bundle_id)
    if _retry_transient_bundle_index(self, bundle_id):
        return {"bundle_id": bundle_id, "status": "index_retry_scheduled"}
    return result


@celery_app.task(name="worker.reindex_bundle", bind=True)
def reindex_bundle(self, bundle_id: str) -> dict[str, str]:
    """Refresh bundle embeddings without reparsing source documents."""
    result = run_reindex(bundle_id)
    if _retry_transient_bundle_index(self, bundle_id):
        return {"bundle_id": bundle_id, "status": "index_retry_scheduled"}
    return result


@celery_app.task(name="worker.poll_due_notice_sources")
def poll_due_notice_sources_task() -> dict[str, int]:
    """Poll configured public tender feeds when their interval is due."""
    return poll_due_notice_sources()


@celery_app.task(name="worker.deliver_due_webhooks")
def deliver_due_webhooks_task() -> dict[str, int]:
    """Recover pending outbound business webhook deliveries."""
    return deliver_due_webhook_deliveries()


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
    max_iterations: int | None = None,
    runtime_run_id: str | None = None,
    deliverable_section_id: str | None = None,
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
                deliverable_section_id=deliverable_section_id,
                provider_config_id=provider_config_id,
                reasoning_effort=reasoning_effort,
                max_iterations=max_iterations or 3,
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

        if result.get("__interrupt__"):
            section_version_id = result.get("section_version_id")
            if not isinstance(section_version_id, str) or not section_version_id:
                message = "工作流请求人工确认时未保存可审核的章节版本。"
                finalize_workflow_model_reservation_failure(
                    run_id=run_id,
                    error_code="workflow_interrupt_without_version",
                )
                _set_execution_status(run_id, "failed", error=message)
                fail_runtime_run(
                    effective_runtime_run_id,
                    message,
                    error_code="workflow_interrupt_without_version",
                )
                return {
                    "status": "error",
                    "run_id": run_id,
                    "section_key": section_key,
                    "error": message,
                }
            _set_execution_status(run_id, "awaiting_human")
            return {
                "status": "awaiting_human",
                "run_id": run_id,
                "section_key": section_key,
                "section_version_id": section_version_id,
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
            "status": "succeeded",
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
            deliverable_section_id=deliverable_section_id,
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
    max_iterations: int | None = None,
    runtime_run_id: str | None = None,
    outbox_event_id: str | None = None,
    deliverable_section_id: str | None = None,
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
            max_iterations=max_iterations,
            runtime_run_id=runtime_run_id,
            deliverable_section_id=deliverable_section_id,
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


@celery_app.task(name="worker.reconcile_runtime_runs")
def reconcile_runtime_runs_task() -> dict[str, str]:
    """Close stale runtime rows after outbox and approval reconciliation."""
    from app.execution.runtime_reconciliation import reconcile_runtime_runs

    return reconcile_runtime_runs()


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
            decision, feedback = resolve_durable_review_resume(
                run_id=run_id,
                requested_decision=decision,
                requested_feedback=feedback,
            )
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

        if result.get("__interrupt__"):
            section_version_id = result.get("section_version_id")
            if not isinstance(section_version_id, str) or not section_version_id:
                message = "恢复后的工作流请求人工确认时未保存可审核的章节版本。"
                finalize_workflow_model_reservation_failure(
                    run_id=run_id,
                    error_code="workflow_resume_interrupt_without_version",
                )
                _set_execution_status(run_id, "failed", error=message)
                fail_runtime_run(
                    runtime_run_id,
                    message,
                    error_code="workflow_resume_interrupt_without_version",
                )
                return {"status": "error", "run_id": run_id, "error": message}
            _set_execution_status(run_id, "awaiting_human")
            return {
                "status": "awaiting_human",
                "run_id": run_id,
                "section_version_id": section_version_id,
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
            "status": "succeeded",
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
