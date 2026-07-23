"""SSE adapter for the explicit LangGraph operator runtime.

The adapter deliberately renders the same legacy ``assistant.*`` events as the
existing web client expects, but those events are derived from durable runtime
records. It is the production default through DOCPILOT_ASSISTANT_ENGINE=operator;
the deterministic adapter remains available only for local and test operation.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
import logging
import os
from typing import Any
from uuid import uuid4

from langgraph.types import Command
from sqlalchemy.orm import Session

from app.assistant.audit import redact_arguments, redact_text
from app.assistant.attachments import attachment_planner_context, build_attachment_context
from app.assistant.schemas import AssistantConfirmation, AssistantRequest
from app.assistant.task_state import clear_task_state, pending_input_context, set_task_state
from app.auth.schemas import CurrentUser
from app.chat.service import (
    bind_conversation_project_context,
    get_conversation_messages,
    resolve_conversation_project_context,
    save_message,
)
from app.memory.schemas import MemoryContextRead
from app.memory.service import memory_context_for_agent
from app.models import RuntimeAction, RuntimeApproval, RuntimeRun
from app.agent.llm import get_agent_llm
from app.usage.schemas import ProviderSource
from app.usage.service import UsageLimitExceeded, reserve_assistant_model_tokens
from contracts.model_usage import ProviderUsageMeasurement
from contracts.usage_ledger import (
    mark_model_reservation_uncertain,
    record_model_usage,
    settle_model_reservation,
)

from .assistant_adapter import (
    _approval_capability,
    _ensure_conversation,
    _is_cancellation_followup,
    _is_confirmation_followup,
    _render_runtime_events,
    _sse,
)
from .events import latest_event_sequence
from .harness_loop import StreamingHarness, stream_harness_assistant_response
from .operator_graph import (
    OperatorPlanningContext,
    OperatorPlan,
    build_langchain_planner,
    build_operator_graph,
    get_operator_checkpointer,
)
from .model_limits import (
    OPERATOR_PLANNER_MAX_CONVERSATION_CONTEXT_CHARACTERS,
    OPERATOR_PLANNER_MAX_CONVERSATION_MESSAGE_CHARACTERS,
    OPERATOR_PLANNER_MAX_MEMORY_CONTEXT_CHARACTERS,
)
from .service import (
    create_runtime_run,
    fail_runtime_run,
    find_pending_approval_for_conversation,
)


def _use_streaming_harness() -> bool:
    """Prefer the thin streaming tool loop unless explicitly disabled."""
    return os.getenv("DOCPILOT_ASSISTANT_STREAMING_HARNESS", "true").lower() == "true"

logger = logging.getLogger(__name__)

_MAX_CONVERSATION_CONTEXT_MESSAGES = 8
_MAX_CONVERSATION_CONTEXT_CHARACTERS = OPERATOR_PLANNER_MAX_CONVERSATION_CONTEXT_CHARACTERS
_MAX_CONVERSATION_MESSAGE_CHARACTERS = OPERATOR_PLANNER_MAX_CONVERSATION_MESSAGE_CHARACTERS


async def stream_operator_assistant_response(
    db: Session,
    user: CurrentUser,
    payload: AssistantRequest,
    *,
    provider_type: str,
    provider_id: str | None,
    provider_source: ProviderSource,
    api_key: str | None,
    base_url: str | None,
    model: str | None,
) -> AsyncGenerator[str, None]:
    """Run one explicit operator graph turn or resume its pending interrupt."""
    conversation_id = _ensure_conversation(db, user, payload)
    active_project_id = resolve_conversation_project_context(
        db,
        user,
        conversation_id=conversation_id,
        requested_project_id=payload.project_id,
    )
    if active_project_id is None and payload.project_id is None:
        active_project_id = _recover_conversation_project_context(db, user, conversation_id)
    if payload.confirmation is not None and payload.confirmation.approval_id:
        save_message(db, conversation_id, "user", payload.message)
        async for event in _resume_operator_approval(
            db,
            user,
            conversation_id,
            payload.confirmation,
            provider_type=provider_type,
            provider_id=provider_id,
            provider_source=provider_source,
            api_key=api_key,
            base_url=base_url,
            model=model,
            reasoning_effort=payload.reasoning_effort,
        ):
            yield event
        return

    pending = find_pending_approval_for_conversation(db, user, conversation_id)
    if pending is not None and _is_confirmation_followup(payload.message):
        save_message(db, conversation_id, "user", payload.message)
        async for event in _resume_operator_approval(
            db,
            user,
            conversation_id,
            AssistantConfirmation(
                approved=not _is_cancellation_followup(payload.message),
                tool_name=_approval_capability(db, pending),
                approval_id=pending.id,
            ),
            provider_type=provider_type,
            provider_id=provider_id,
            provider_source=provider_source,
            api_key=api_key,
            base_url=base_url,
            model=model,
            reasoning_effort=payload.reasoning_effort,
        ):
            yield event
        return

    conversation_context = _bounded_conversation_context(db, conversation_id)
    pending_input = pending_input_context(db, conversation_id)
    memory_context = _load_authorized_memory_context(db, user, payload, project_id=active_project_id)
    save_message(db, conversation_id, "user", payload.message)
    engine = "streaming_harness" if _use_streaming_harness() else "langgraph_operator"
    run = create_runtime_run(
        db,
        user,
        kind="assistant_turn",
        engine=engine,
        project_id=active_project_id,
        conversation_id=conversation_id,
        provider_config_id=payload.provider_config_id,
        model=model,
        reasoning_effort=payload.reasoning_effort,
        approval_mode=payload.approval_mode,
        input_json={
            "message": payload.message,
            "attachment_names": [attachment.name for attachment in payload.attachments],
            "attachment_ids": [attachment.id for attachment in payload.attachments if attachment.id],
        },
    )
    yield _sse(
        "assistant.start",
        {"conversation_id": conversation_id, "runtime_run_id": run.id, "state": "thinking"},
    )
    if engine == "streaming_harness":
        llm = get_agent_llm(
            provider_type=provider_type,
            provider_id=provider_id,
            api_key=api_key,
            base_url=base_url,
            model=model,
            reasoning_effort=payload.reasoning_effort,  # type: ignore[arg-type]
        )
        memory_records = []
        if memory_context is not None:
            from .operator_graph import _memory_context_records

            memory_records = _memory_context_records(memory_context)
        async for event in stream_harness_assistant_response(
            db,
            user,
            run=run,
            conversation_id=conversation_id,
            llm=llm,
            provider_type=provider_type,
            provider_source=provider_source,
            model=model,
            user_message=build_attachment_context(payload.message, payload.attachments),
            conversation_context=conversation_context,
            memory_context_records=memory_records,
            available_attachments=attachment_planner_context(payload.attachments),
            active_project_id=active_project_id,
            pending_input=pending_input,
            provider_config_id=payload.provider_config_id,
            reasoning_effort=payload.reasoning_effort,
            after_sequence=1,
        ):
            yield event
        return

    async for event in _invoke_operator_graph(
        db,
        user,
        run,
        conversation_id,
        user_message=build_attachment_context(payload.message, payload.attachments),
        provider_type=provider_type,
        provider_id=provider_id,
        provider_source=provider_source,
        api_key=api_key,
        base_url=base_url,
        model=model,
        reasoning_effort=payload.reasoning_effort,
        conversation_context=conversation_context,
        memory_context=memory_context,
        available_attachments=attachment_planner_context(payload.attachments),
        active_project_id=active_project_id,
        pending_input=pending_input,
    ):
        yield event


async def _resume_operator_approval(
    db: Session,
    user: CurrentUser,
    conversation_id: str,
    confirmation: AssistantConfirmation,
    *,
    provider_type: str,
    provider_id: str | None,
    provider_source: ProviderSource,
    api_key: str | None,
    base_url: str | None,
    model: str | None,
    reasoning_effort: str | None,
) -> AsyncGenerator[str, None]:
    approval = db.get(RuntimeApproval, confirmation.approval_id)
    action = db.get(RuntimeAction, approval.action_id) if approval is not None else None
    run = db.get(RuntimeRun, action.run_id) if action is not None else None
    if (
        approval is None
        or action is None
        or run is None
        or approval.user_id != user.id
        or approval.org_id != user.org_id
        or run.conversation_id != conversation_id
        or run.engine not in {"langgraph_operator", "streaming_harness"}
    ):
        yield _sse(
            "assistant.tool_failed",
            {"tool_name": confirmation.tool_name, "error_message": "未找到当前会话的待处理审批。", "state": "failed"},
        )
        yield _sse("assistant.end", {"conversation_id": conversation_id, "state": "failed"})
        return

    before_sequence = latest_event_sequence(db, run.id)
    yield _sse(
        "assistant.start",
        {"conversation_id": conversation_id, "runtime_run_id": run.id, "state": "thinking"},
    )
    if run.engine == "streaming_harness":
        harness = StreamingHarness(
            db=db,
            user=user,
            run=run,
            conversation_id=conversation_id,
            llm=None,
            provider_type=provider_type,
            provider_source=provider_source,
            model=model,
            user_message="",
            after_sequence=before_sequence,
        )
        edited_arguments = (
            dict(confirmation.arguments)
            if confirmation.approved and confirmation.arguments
            else None
        )
        async for event in harness.resume_approval(
            approval_id=approval.id,
            approved=bool(confirmation.approved),
            tool_name=confirmation.tool_name or action.capability_name,
            edited_arguments=edited_arguments,
        ):
            yield event
        return

    decision = "approve" if confirmation.approved else "reject"
    async for event in _invoke_operator_graph(
        db,
        user,
        run,
        conversation_id,
        user_message="",
        provider_type=provider_type,
        provider_id=provider_id,
        provider_source=provider_source,
        api_key=api_key,
        base_url=base_url,
        model=model,
        reasoning_effort=reasoning_effort,
        resume_value={"decision": decision},
        after_sequence=before_sequence,
    ):
        yield event


async def _invoke_operator_graph(
    db: Session,
    user: CurrentUser,
    run: RuntimeRun,
    conversation_id: str,
    *,
    user_message: str,
    provider_type: str,
    provider_id: str | None,
    provider_source: ProviderSource,
    api_key: str | None,
    base_url: str | None,
    model: str | None,
    reasoning_effort: str | None,
    conversation_context: list[dict[str, str]] | None = None,
    memory_context: MemoryContextRead | None = None,
    available_attachments: list[dict[str, str | int]] | None = None,
    active_project_id: str | None = None,
    pending_input: dict[str, Any] | None = None,
    resume_value: dict[str, Any] | None = None,
    after_sequence: int = 1,
) -> AsyncGenerator[str, None]:
    active_reservation_keys: list[str] = []

    def reserve_planner_capacity(_context: OperatorPlanningContext) -> None:
        """Commit one pre-dispatch hold without retaining a DB lock over I/O."""
        reservation_key = f"assistant:{run.id}:{uuid4()}"
        reservation = reserve_assistant_model_tokens(
            db,
            user_id=user.id,
            org_id=user.org_id,
            provider_source=provider_source,
            reservation_key=reservation_key,
            project_id=run.project_id,
            runtime_run_id=run.id,
        )
        if reservation is None:
            return
        try:
            db.commit()
        except Exception:
            db.rollback()
            raise
        active_reservation_keys.append(reservation_key)

    def mark_active_reservations_uncertain() -> None:
        if not active_reservation_keys:
            return
        keys = tuple(active_reservation_keys)
        active_reservation_keys.clear()
        try:
            for reservation_key in keys:
                mark_model_reservation_uncertain(
                    db,
                    org_id=user.org_id,
                    reservation_key=reservation_key,
                )
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("Failed to mark assistant model reservations uncertain: runtime_run=%s", run.id)

    def observe_model_usage(measurement: ProviderUsageMeasurement | None) -> None:
        reservation_key = active_reservation_keys.pop() if active_reservation_keys else None
        try:
            if measurement is not None:
                record_model_usage(
                    db,
                    org_id=user.org_id,
                    user_id=user.id,
                    project_id=run.project_id,
                    runtime_run_id=run.id,
                    provider_source=provider_source.value,  # type: ignore[arg-type]
                    provider_type=provider_type,
                    provider_config_id=run.provider_config_id,
                    model_name=model or run.model or "platform-default",
                    workload="assistant_planning",
                    measurement=measurement,
                )
            if reservation_key is not None:
                if measurement is None:
                    mark_model_reservation_uncertain(
                        db,
                        org_id=user.org_id,
                        reservation_key=reservation_key,
                    )
                else:
                    settle_model_reservation(
                        db,
                        org_id=user.org_id,
                        reservation_key=reservation_key,
                    )
            if measurement is not None or reservation_key is not None:
                db.commit()
        except Exception:
            db.rollback()
            if reservation_key is not None:
                try:
                    mark_model_reservation_uncertain(
                        db,
                        org_id=user.org_id,
                        reservation_key=reservation_key,
                    )
                    db.commit()
                except Exception:
                    db.rollback()
            logger.exception("Failed to persist assistant model usage: runtime_run=%s", run.id)

    try:
        llm = get_agent_llm(
            provider_type=provider_type,
            provider_id=provider_id,
            api_key=api_key,
            base_url=base_url,
            model=model,
            reasoning_effort=reasoning_effort,  # type: ignore[arg-type]
        )
        graph = build_operator_graph(
            db,
            user,
            planner=build_langchain_planner(
                llm,
                memory_context=memory_context,
                on_model_usage=observe_model_usage,
                before_model_call=reserve_planner_capacity,
            ),
            checkpointer=get_operator_checkpointer(),
        )
        config = {"configurable": {"thread_id": conversation_id}}
        if resume_value is None:
            result = graph.invoke(
                {
                    "runtime_run_id": run.id,
                    "user_message": user_message,
                    "conversation_context": conversation_context or [],
                    "available_attachments": available_attachments or [],
                    "active_project_id": active_project_id,
                    "pending_input": pending_input or {},
                    "calls_made": 0,
                    "plan": {},
                    "last_result": {},
                    "continue_planning": False,
                    "final_message": "",
                    "terminal_status": "succeeded",
                },
                config=config,
            )
        else:
            result = graph.invoke(Command(resume=resume_value), config=config)
    except UsageLimitExceeded as exc:
        mark_active_reservations_uncertain()
        message = str(exc)
        try:
            fail_runtime_run(db, run.id, message, error_code="organization_token_budget_exhausted")
        except ValueError:
            pass
        save_message(db, conversation_id, "assistant", message)
        for event in _render_runtime_events(
            db,
            run.id,
            after_sequence=after_sequence,
            conversation_id=conversation_id,
        ):
            yield event
        return
    except Exception as exc:
        mark_active_reservations_uncertain()
        safe_error = redact_text(str(exc))
        try:
            fail_runtime_run(db, run.id, f"执行失败：{safe_error}", error_code="operator_graph_failed")
        except ValueError:
            pass
        save_message(db, conversation_id, "assistant", f"执行失败：{safe_error}")
        for event in _render_runtime_events(
            db,
            run.id,
            after_sequence=after_sequence,
            conversation_id=conversation_id,
        ):
            yield event
        return

    _sync_pending_input_state(db, conversation_id, result)

    if result.get("__interrupt__"):
        for event in _render_runtime_events(
            db,
            run.id,
            after_sequence=after_sequence,
            conversation_id=conversation_id,
        ):
            yield event
        yield _sse(
            "assistant.end",
            {"conversation_id": conversation_id, "runtime_run_id": run.id, "state": "needs_confirmation"},
        )
        return

    _bind_created_project_to_conversation(db, user, conversation_id, run.id)
    message = str(result.get("final_message") or "")
    if message:
        save_message(db, conversation_id, "assistant", message)
    for event in _render_runtime_events(
        db,
        run.id,
        after_sequence=after_sequence,
        conversation_id=conversation_id,
    ):
        yield event


def _bounded_conversation_context(db: Session, conversation_id: str) -> list[dict[str, str]]:
    """Load recent public chat turns without treating checkpoint state as business truth."""
    remaining = _MAX_CONVERSATION_CONTEXT_CHARACTERS
    items: list[dict[str, str]] = []
    messages = get_conversation_messages(db, conversation_id)[-_MAX_CONVERSATION_CONTEXT_MESSAGES:]
    for message in reversed(messages):
        if remaining <= 0:
            break
        content = message.content.strip()
        if not content:
            continue
        limit = min(_MAX_CONVERSATION_MESSAGE_CHARACTERS, remaining)
        items.append(
            {
                "role": message.role if message.role in {"user", "assistant"} else "user",
                "content": content[:limit],
            }
        )
        remaining -= len(items[-1]["content"])
    return list(reversed(items))


def _load_authorized_memory_context(
    db: Session,
    user: CurrentUser,
    payload: AssistantRequest,
    *,
    project_id: str | None,
) -> MemoryContextRead | None:
    """Memory retrieval is additive and cannot make an Operator turn fail."""
    try:
        return memory_context_for_agent(
            db,
            current_user=user,
            project_id=project_id,
            query=payload.message,
            top_k=4,
            max_characters=OPERATOR_PLANNER_MAX_MEMORY_CONTEXT_CHARACTERS,
        )
    except Exception as exc:
        logger.warning("Operator memory context unavailable: %s", type(exc).__name__)
        return None


def _bind_created_project_to_conversation(
    db: Session,
    user: CurrentUser,
    conversation_id: str,
    run_id: str,
) -> None:
    """Persist the project created by this turn as its future conversation scope."""
    action = (
        db.query(RuntimeAction)
        .filter(
            RuntimeAction.run_id == run_id,
            RuntimeAction.capability_name.in_(("create_project", "create_demo_workspace")),
            RuntimeAction.status == "succeeded",
        )
        .order_by(RuntimeAction.completed_at.desc())
        .first()
    )
    project_id = (action.result_json or {}).get("id") if action is not None else None
    if isinstance(project_id, str) and project_id:
        bind_conversation_project_context(
            db,
            conversation_id=conversation_id,
            user_id=user.id,
            project_id=project_id,
        )


def _recover_conversation_project_context(
    db: Session,
    user: CurrentUser,
    conversation_id: str,
) -> str | None:
    """Backfill a legacy conversation from its own successful create action."""
    action = (
        db.query(RuntimeAction)
        .join(RuntimeRun, RuntimeAction.run_id == RuntimeRun.id)
        .filter(
            RuntimeRun.conversation_id == conversation_id,
            RuntimeRun.user_id == user.id,
            RuntimeRun.org_id == user.org_id,
            RuntimeAction.capability_name.in_(("create_project", "create_demo_workspace")),
            RuntimeAction.status == "succeeded",
        )
        .order_by(RuntimeAction.completed_at.desc())
        .first()
    )
    project_id = (action.result_json or {}).get("id") if action is not None else None
    if not isinstance(project_id, str) or not project_id:
        return None

    bind_conversation_project_context(
        db,
        conversation_id=conversation_id,
        user_id=user.id,
        project_id=project_id,
    )
    return project_id


def _sync_pending_input_state(
    db: Session,
    conversation_id: str,
    result: dict[str, Any],
) -> None:
    """Persist the planner's structured continuation boundary, not its prose."""
    try:
        plan = OperatorPlan.model_validate(result.get("plan") or {})
    except ValueError:
        return
    if plan.mode == "needs_input":
        set_task_state(
            db,
            conversation_id,
            status="needs_input",
            tool_name=plan.capability_name,
            arguments=redact_arguments(plan.arguments),
            missing_fields=plan.missing_fields,
        )
        return
    clear_task_state(db, conversation_id)
