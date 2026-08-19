"""SSE facade for governed assistant turns.

New turns are dispatched to the Pi sidecar. This module retains the durable
run/idempotency/approval facade and historical replay paths, while the old
Python loop is not an automatic fallback for new requests.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
import logging
from typing import Any
from uuid import uuid4

from langgraph.types import Command
from sqlalchemy.orm import Session

from app.assistant.audit import redact_arguments
from app.assistant.attachments import attachment_planner_context, build_attachment_context
from app.assistant.schemas import AssistantConfirmation, AssistantRequest
from app.assistant.task_state import clear_task_state, pending_input_context, set_task_state
from app.auth.schemas import CurrentUser
from app.chat.service import (
    bind_conversation_project_context,
    get_recent_conversation_messages,
    resolve_conversation_project_context,
    save_message,
)
from app.memory.schemas import MemoryContextRead
from app.memory.service import memory_context_for_agent
from app.models import RuntimeAction, RuntimeApproval, RuntimeEvent, RuntimeRun
from app.agent.llm import get_agent_llm
from app.usage.schemas import ProviderSource
from app.usage.service import UsageLimitExceeded, reserve_assistant_model_tokens
from contracts.model_usage import ProviderUsageMeasurement
from contracts.runtime import RuntimeApprovalDecisionType
from contracts.usage_ledger import (
    mark_model_reservation_uncertain,
    record_model_usage,
    settle_model_reservation,
)

from .assistant_adapter import (
    _approval_capability,
    _ensure_conversation,
    _matches_typed_confirmation,
    _pending_approval_status_reply,
    _render_runtime_events,
    _sse,
)
from .events import latest_event_sequence
from .pi_adapter import stream_pi_assistant_response
from .operator_graph import (
    OperatorPlanningContext,
    OperatorPlan,
    build_langchain_planner,
    build_operator_graph,
    get_operator_checkpointer,
)
from .model_limits import (
    OPERATOR_PLANNER_MAX_MEMORY_CONTEXT_CHARACTERS,
)
from .prompt_assembly import ConversationContextWindow, compact_conversation_context
from .service import (
    assistant_turn_idempotency_key,
    complete_runtime_run,
    create_or_get_runtime_run,
    fail_runtime_run,
    find_idempotent_runtime_run,
    find_pending_approval_for_conversation,
    reconcile_runtime_run_for_replay,
    resolve_approval,
)


logger = logging.getLogger(__name__)

_MAX_CONVERSATION_SOURCE_MESSAGES = 24


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
    """Run one governed Harness turn or resume its pending approval."""
    # Check retries before allocating a conversation. The first SSE response may
    # be interrupted before the browser receives its conversation ID; creating
    # one here would leave an orphan conversation for every retry.
    idempotency_key = assistant_turn_idempotency_key(
        user_id=user.id,
        client_request_id=payload.client_request_id,
    )
    if payload.confirmation is None:
        existing = find_idempotent_runtime_run(
            db,
            user,
            idempotency_key=idempotency_key,
        )
        if existing is not None:
            async for event in _replay_existing_run(
                db,
                existing,
                conversation_id=existing.conversation_id or payload.conversation_id or "",
            ):
                yield event
            return

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
    # Typed delete confirmation: user retyped the exact project name.
    if pending is not None and _matches_typed_confirmation(pending, payload.message):
        save_message(db, conversation_id, "user", payload.message)
        pending_payload = pending.payload_json if isinstance(pending.payload_json, dict) else {}
        pending_arguments = pending_payload.get("arguments")
        confirmed_arguments = pending_arguments if isinstance(pending_arguments, dict) else {}
        async for event in _resume_operator_approval(
            db,
            user,
            conversation_id,
            AssistantConfirmation(
                approved=True,
                tool_name=_approval_capability(db, pending),
                approval_id=pending.id,
                arguments={
                    **confirmed_arguments,
                    "confirmation_text": payload.message.strip(),
                },
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

    # Any other free-text while approval is pending must not start a new tool loop
    # that forgets the pending delete / write. Re-surface the confirmation instead.
    if pending is not None:
        save_message(db, conversation_id, "user", payload.message)
        reply = _pending_approval_status_reply(pending)
        save_message(db, conversation_id, "assistant", reply)
        payload_json = pending.payload_json if isinstance(pending.payload_json, dict) else {}
        yield _sse(
            "assistant.start",
            {"conversation_id": conversation_id, "state": "needs_confirmation"},
        )
        yield _sse(
            "assistant.message",
            {"content": reply, "state": "needs_confirmation"},
        )
        confirmation = {
            "approval_id": pending.id,
            "tool_name": _approval_capability(db, pending),
            "arguments": payload_json.get("arguments") or {},
            "message": payload_json.get("message") or reply,
            "requires_typed_confirmation": bool(payload_json.get("requires_typed_confirmation")),
            "state": "needs_confirmation",
        }
        if isinstance(payload_json.get("expected_text"), str):
            confirmation["expected_text"] = payload_json["expected_text"]
        yield _sse("assistant.confirmation_requested", confirmation)
        yield _sse(
            "assistant.end",
            {"conversation_id": conversation_id, "state": "needs_confirmation"},
        )
        return

    conversation_window = _bounded_conversation_context(db, conversation_id)
    pending_input = pending_input_context(db, conversation_id)
    memory_context = _load_authorized_memory_context(db, user, payload, project_id=active_project_id)
    creation = create_or_get_runtime_run(
        db,
        user,
        kind="assistant_turn",
        engine="pi",
        project_id=active_project_id,
        conversation_id=conversation_id,
        provider_config_id=payload.provider_config_id,
        model=model,
        reasoning_effort=payload.reasoning_effort,
        approval_mode=payload.approval_mode,
        idempotency_key=idempotency_key,
        input_json={
            "message": payload.message,
            "client_request_id": payload.client_request_id,
            "attachment_names": [attachment.name for attachment in payload.attachments],
            "attachment_ids": [attachment.id for attachment in payload.attachments if attachment.id],
        },
    )
    if not creation.created:
        async for event in _replay_existing_run(
            db,
            creation.run,
            conversation_id=creation.run.conversation_id or conversation_id,
        ):
            yield event
        return

    run = creation.run
    user_message = save_message(
        db,
        conversation_id,
        "user",
        payload.message,
        attachments=payload.attachments,
    )
    yield _sse(
        "assistant.start",
        {
            "conversation_id": conversation_id,
            "runtime_run_id": run.id,
            "user_message_id": user_message.id,
            "state": "thinking",
        },
    )
    memory_records = []
    if memory_context is not None:
        from .operator_graph import _memory_context_records

        memory_records = _memory_context_records(memory_context)
    async for event in stream_pi_assistant_response(
        db,
        user,
        run=run,
        conversation_id=conversation_id,
        provider_type=provider_type,
        provider_id=provider_id,
        api_key=api_key,
        base_url=base_url,
        model=model,
        user_message=payload.message,
        conversation_window=conversation_window,
        memory_context_records=memory_records,
        memory_context_version=memory_context.memory_version if memory_context is not None else None,
        available_attachments=attachment_planner_context(payload.attachments),
        attachment_context=build_attachment_context("", payload.attachments),
        active_project_id=active_project_id,
        pending_input=pending_input,
        approval_mode=payload.approval_mode,
        reasoning_effort=payload.reasoning_effort,
    ):
        yield event
    return


async def _replay_existing_run(
    db: Session,
    run: RuntimeRun,
    *,
    conversation_id: str,
) -> AsyncGenerator[str, None]:
    """Replay a durable run after a client retry without re-entering the loop."""
    run = reconcile_runtime_run_for_replay(db, run.id)
    state_by_status = {
        "awaiting_approval": "needs_confirmation",
        "failed": "failed",
        "expired": "failed",
        "cancelled": "completed",
        "succeeded": "completed",
    }
    state = state_by_status.get(run.status, "thinking")
    yield _sse(
        "assistant.start",
        {
            "conversation_id": conversation_id,
            "runtime_run_id": run.id,
            "state": state,
            "replayed": True,
        },
    )
    emitted_end = False
    for event in _render_runtime_events(
        db,
        run.id,
        after_sequence=0,
        conversation_id=conversation_id,
    ):
        if event.startswith("event: assistant.end"):
            emitted_end = True
        yield event
    if not emitted_end:
        yield _sse(
            "assistant.end",
            {
                "conversation_id": conversation_id,
                "runtime_run_id": run.id,
                "state": state,
                "replayed": True,
            },
        )


async def stream_existing_assistant_run(
    db: Session,
    run: RuntimeRun,
) -> AsyncGenerator[str, None]:
    """Replay a previously authorized assistant run without resolving a model."""
    conversation_id = run.conversation_id
    if not conversation_id:
        logger.error("Idempotent assistant run has no conversation: runtime_run=%s", run.id)
        yield _sse(
            "assistant.end",
            {"runtime_run_id": run.id, "state": "failed", "replayed": True},
        )
        return
    async for event in _replay_existing_run(db, run, conversation_id=conversation_id):
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
        or run.engine not in {"langgraph_operator", "streaming_harness", "pi"}
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
    if run.engine == "pi":
        if confirmation.approved:
            decision = (
                RuntimeApprovalDecisionType.EDIT
                if confirmation.arguments
                else RuntimeApprovalDecisionType.APPROVE
            )
        else:
            decision = RuntimeApprovalDecisionType.REJECT
        execution = resolve_approval(
            db,
            user,
            approval_id=approval.id,
            decision=decision,
            edited_arguments=(dict(confirmation.arguments) if confirmation.arguments else None),
        )
        if confirmation.approved and execution.result is not None:
            reply = execution.result.summary
        elif confirmation.approved:
            reply = "已执行确认的操作。"
        else:
            reply = "已取消该操作。"
            run.status = "running"
            db.commit()
        save_message(db, conversation_id, "assistant", reply)
        complete_runtime_run(db, run.id, reply)
        for event in _render_runtime_events(
            db,
            run.id,
            after_sequence=before_sequence,
            conversation_id=conversation_id,
        ):
            yield event
        return
    if run.engine == "streaming_harness":
        from .harness_loop import StreamingHarness

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
        try:
            # A budget lookup still locks the organization row when the
            # workspace has no configured ceiling. Do not retain that lock for
            # the lifetime of a planner invocation.
            db.commit()
        except Exception:
            db.rollback()
            raise
        if reservation is not None:
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
        from .harness_loop import classify_model_failure

        failure = classify_model_failure(exc)
        message = f"执行失败：{failure.message}"
        try:
            fail_runtime_run(db, run.id, message, error_code=failure.error_code)
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


def _bounded_conversation_context(db: Session, conversation_id: str) -> ConversationContextWindow:
    """Load recent transcript rows plus any runtime-only terminal replies.

    A disconnected SSE stream can leave ``message.completed`` durable while
    the corresponding ``chat_messages`` row was never committed. The runtime
    event is redacted public text, so it is a valid transcript projection for
    the next model turn and prevents the UI/model from diverging.
    """
    limit = _MAX_CONVERSATION_SOURCE_MESSAGES
    messages, history_window_truncated = get_recent_conversation_messages(
        db,
        conversation_id,
        limit=limit,
    )
    source: list[tuple[float, str, str]] = [
        (
            message.created_at.timestamp() if message.created_at is not None else 0.0,
            message.role,
            _message_with_attachment_context(message),
        )
        for message in messages
    ]
    known_contents = {content.strip() for _, _, content in source if content.strip()}
    runtime_messages = (
        db.query(RuntimeEvent)
        .join(RuntimeRun, RuntimeEvent.run_id == RuntimeRun.id)
        .filter(
            RuntimeRun.conversation_id == conversation_id,
            RuntimeEvent.event_type == "message.completed",
        )
        .order_by(RuntimeEvent.created_at.asc(), RuntimeEvent.sequence.asc())
        .limit(limit + 1)
        .all()
    )
    for event in runtime_messages:
        content = event.public_summary.strip()
        if not content or content in known_contents:
            continue
        known_contents.add(content)
        source.append(
            (
                event.created_at.timestamp() if event.created_at is not None else 0.0,
                "assistant",
                content,
            )
        )
    source.sort(key=lambda item: item[0])
    if len(source) > limit:
        history_window_truncated = True
        source = source[-limit:]
    return compact_conversation_context(
        [
            {
                "role": role,
                "content": content,
            }
            for _, role, content in source
        ],
        history_window_truncated=history_window_truncated,
    )


def _message_with_attachment_context(message: object) -> str:
    """Keep prior turn attachments in the bounded, untrusted chat trajectory."""
    content = str(getattr(message, "content", "")).strip()
    attachments = getattr(message, "attachments", ()) or ()
    sections: list[str] = []
    for attachment in attachments:
        text = str(getattr(attachment, "extracted_text", "") or "").strip()
        if not text:
            continue
        name = str(getattr(attachment, "name", "附件"))[:255]
        sections.append(f"历史附件《{name}》可读正文：\n{text}")
    return "\n\n".join([content, *sections]).strip()


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
