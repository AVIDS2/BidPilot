"""Background Mem0 profile capture for completed Pi assistant runs."""

from __future__ import annotations

import logging

from sqlalchemy import select

from app.db import SessionLocal
from app.memory.mem0_provider import (
    capture_profile_memory,
    delete_profile_memory,
    mem0_enabled,
    mem0_profile_fingerprint,
)
from app.models import ChatMessage, Mem0ProfileSync, RuntimeRun


logger = logging.getLogger(__name__)


def capture_mem0_profile_for_run(runtime_run_id: str) -> dict[str, object]:
    """Submit one successful run for low-risk profile extraction.

    This task never affects the assistant run status. Mem0 is an optional
    personalization service, and the local ledger makes delivery idempotent
    without storing conversation text in BidPilot's sync table.
    """

    if not mem0_enabled():
        return {"status": "disabled", "runtime_run_id": runtime_run_id}

    db = SessionLocal()
    try:
        run = db.get(RuntimeRun, runtime_run_id)
        if run is None or run.status != "succeeded" or not run.conversation_id:
            return {"status": "skipped", "runtime_run_id": runtime_run_id}
        input_json = run.input_json if isinstance(run.input_json, dict) else {}
        user_message_id = input_json.get("user_message_id")
        user_message = db.get(ChatMessage, user_message_id) if isinstance(user_message_id, str) else None
        assistant_message = db.scalar(
            select(ChatMessage)
            .where(
                ChatMessage.runtime_run_id == run.id,
                ChatMessage.role == "assistant",
            )
            .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
            .limit(1)
        )
        if user_message is None or assistant_message is None:
            return {"status": "skipped", "runtime_run_id": runtime_run_id, "reason": "messages_missing"}

        messages = [
            {"role": "user", "content": user_message.content},
            {"role": "assistant", "content": assistant_message.content},
        ]
        fingerprint = mem0_profile_fingerprint(
            user_id=run.user_id,
            org_id=run.org_id,
            run_id=run.id,
            messages=messages,
        )
        sync = db.scalar(
            select(Mem0ProfileSync)
            .where(
                Mem0ProfileSync.runtime_run_id == run.id,
                Mem0ProfileSync.provider == "mem0_platform",
            )
            .with_for_update()
        )
        if sync is not None and sync.status in {"submitted", "succeeded"}:
            return {"status": "duplicate", "runtime_run_id": runtime_run_id}
        if sync is None:
            sync = Mem0ProfileSync(
                org_id=run.org_id,
                user_id=run.user_id,
                runtime_run_id=run.id,
                conversation_id=run.conversation_id,
                content_fingerprint=fingerprint,
                status="running",
            )
            db.add(sync)
        else:
            sync.content_fingerprint = fingerprint
            sync.status = "running"
            sync.error_code = None
        db.commit()
        db.refresh(sync)

        result = capture_profile_memory(
            user_id=run.user_id,
            org_id=run.org_id,
            run_id=run.id,
            messages=messages,
        )
        sync.status = "submitted" if result.get("status") == "queued" else str(result.get("status") or "failed")
        sync.external_event_id = str(result["event_id"]) if result.get("event_id") else None
        sync.error_code = None if sync.status in {"submitted", "succeeded", "skipped", "disabled"} else "mem0_capture_failed"
        db.commit()
        return {"status": sync.status, "runtime_run_id": runtime_run_id}
    except Exception:  # noqa: BLE001 - profile capture must never fail Pi delivery
        db.rollback()
        logger.exception("Mem0 profile capture bookkeeping failed: run=%s", runtime_run_id)
        return {"status": "failed", "runtime_run_id": runtime_run_id}
    finally:
        db.close()


def delete_mem0_profile_for_user(*, user_id: str, org_ids: list[str]) -> dict[str, object]:
    """Delete the user's BidPilot-scoped profile memories after account deletion."""

    if not mem0_enabled():
        return {"status": "disabled", "user_id": user_id}
    results: list[str] = []
    for org_id in sorted({item for item in org_ids if item}):
        result = delete_profile_memory(user_id=user_id, org_id=org_id)
        results.append(str(result.get("status") or "failed"))
    return {"status": "deleted" if results and all(item == "deleted" for item in results) else "failed", "user_id": user_id}


__all__ = ["capture_mem0_profile_for_run", "delete_mem0_profile_for_user"]
