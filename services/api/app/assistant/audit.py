"""Assistant action audit and approval persistence."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.policy import ApprovalMode, get_tool_policy
from app.auth.schemas import CurrentUser
from app.models import AssistantActionAudit, AssistantApproval


SENSITIVE_ARGUMENT_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "access_token",
    "refresh_token",
    "password",
    "passphrase",
    "private_key",
    "secret",
    "credential",
    "connection_string",
    "dsn",
    "signing_key",
    "token",
}

VALID_APPROVAL_MODES: set[str] = {"request_approval", "risky_only", "full_access", "custom"}
SECRET_TEXT_PATTERNS = [
    re.compile(r"(?i)\bbearer\s+[a-z0-9._\-]+"),
    re.compile(r"\bsk-[A-Za-z0-9._\-]{12,}"),
    re.compile(
        r"(?i)\b(api[_-]?key|access[_-]?token|refresh[_-]?token|authorization|password|"
        r"secret|credential|private[_-]?key|passphrase|connection[_-]?string|dsn|signing[_-]?key)"
        r"\s*[:=]\s*['\"]?[^'\"\s,;]+"
    ),
]


def record_action_started(
    db: Session,
    user: CurrentUser,
    *,
    conversation_id: str,
    tool_name: str,
    arguments: dict[str, Any],
    approval_mode: ApprovalMode,
) -> AssistantActionAudit:
    """Create a running action audit row before executing a tool."""
    approval_mode = validate_approval_mode(approval_mode)
    audit = AssistantActionAudit(
        conversation_id=conversation_id,
        user_id=user.id,
        org_id=_org_id(user),
        tool_name=tool_name,
        risk_level=_risk_level(tool_name),
        approval_mode=approval_mode,
        arguments_json=redact_arguments(arguments),
        status="running",
    )
    db.add(audit)
    db.commit()
    db.refresh(audit)
    return audit


def record_pending_approval(
    db: Session,
    user: CurrentUser,
    *,
    conversation_id: str,
    tool_name: str,
    arguments: dict[str, Any],
    approval_mode: ApprovalMode,
    payload: dict[str, Any],
    ttl: timedelta = timedelta(minutes=30),
) -> AssistantApproval:
    """Persist a pending approval mirror for a guarded action."""
    approval_mode = validate_approval_mode(approval_mode)
    now = _now()
    audit = AssistantActionAudit(
        conversation_id=conversation_id,
        user_id=user.id,
        org_id=_org_id(user),
        tool_name=tool_name,
        risk_level=_risk_level(tool_name),
        approval_mode=approval_mode,
        arguments_json=redact_arguments(arguments),
        status="pending_approval",
    )
    db.add(audit)
    db.flush()

    approval = AssistantApproval(
        conversation_id=conversation_id,
        action_audit_id=audit.id,
        user_id=user.id,
        org_id=_org_id(user),
        thread_id=conversation_id,
        tool_name=tool_name,
        risk_level=audit.risk_level,
        payload_json=_redacted_payload(payload),
        status="pending",
        expires_at=now + ttl,
    )
    db.add(approval)
    db.commit()
    db.refresh(approval)
    return approval


def record_action_needs_approval(
    db: Session,
    user: CurrentUser,
    audit: AssistantActionAudit,
    *,
    payload: dict[str, Any],
    ttl: timedelta = timedelta(minutes=30),
) -> AssistantApproval:
    """Turn an already-started guarded tool call into a pending approval."""
    now = _now()
    arguments = payload.get("arguments") if isinstance(payload.get("arguments"), dict) else {}
    audit.status = "pending_approval"
    audit.arguments_json = {
        **(audit.arguments_json or {}),
        **redact_arguments(arguments),
    }
    audit.completed_at = None

    approval = AssistantApproval(
        conversation_id=audit.conversation_id,
        action_audit_id=audit.id,
        user_id=user.id,
        org_id=_org_id(user),
        thread_id=audit.conversation_id,
        tool_name=audit.tool_name,
        risk_level=audit.risk_level,
        payload_json=_redacted_payload(payload),
        status="pending",
        expires_at=now + ttl,
    )
    db.add(approval)
    db.commit()
    db.refresh(approval)
    return approval


def begin_confirmed_action(
    db: Session,
    user: CurrentUser,
    *,
    conversation_id: str,
    tool_name: str,
    arguments: dict[str, Any],
    approval_id: str | None,
    approval_mode: ApprovalMode = "risky_only",
) -> AssistantActionAudit:
    """Move a pending approval audit into running, or create one for direct confirmations."""
    approval_mode = validate_approval_mode(approval_mode)
    approval = _find_pending_approval(db, user, conversation_id, tool_name, approval_id)
    now = _now()
    if approval is not None:
        audit = db.get(AssistantActionAudit, approval.action_audit_id)
        if audit is None:
            approval.status = "failed"
            approval.resolved_at = now
            db.commit()
            raise ValueError("审批数据异常，请重新发起操作。")
        approval.status = "approved"
        approval.resolved_at = now
        audit.status = "running"
        audit.arguments_json = redact_arguments(arguments)
        db.commit()
        db.refresh(audit)
        return audit
    if approval_id is not None:
        raise ValueError("审批已过期或不可用，请重新发起操作。")

    return record_action_started(
        db,
        user,
        conversation_id=conversation_id,
        tool_name=tool_name,
        arguments=arguments,
        approval_mode=approval_mode,
    )


def cancel_pending_action(
    db: Session,
    user: CurrentUser,
    *,
    conversation_id: str,
    tool_name: str,
    approval_id: str | None = None,
) -> None:
    """Mark the latest pending approval and its audit row as cancelled."""
    approval = _find_pending_approval(
        db,
        user,
        conversation_id,
        tool_name,
        approval_id,
        fail_on_expired=False,
    )
    if approval is None:
        return
    now = _now()
    approval.status = "cancelled"
    approval.resolved_at = now
    audit = db.get(AssistantActionAudit, approval.action_audit_id)
    if audit is not None:
        audit.status = "cancelled"
        audit.completed_at = now
    db.commit()


def record_action_succeeded(db: Session, audit: AssistantActionAudit, summary: str) -> None:
    audit.status = "succeeded"
    audit.result_summary = redact_text(summary)
    audit.error_message = None
    audit.completed_at = _now()
    db.commit()


def record_action_failed(db: Session, audit: AssistantActionAudit, error_message: str) -> None:
    audit.status = "failed"
    audit.error_message = redact_text(error_message)
    audit.completed_at = _now()
    db.commit()


def redact_arguments(value: Any) -> Any:
    """Return a deep-redacted copy of nested tool arguments."""
    if isinstance(value, dict):
        return {
            key: "***redacted***" if _is_sensitive_key(key) else redact_arguments(child)
            for key, child in value.items()
        }
    if isinstance(value, list):
        return [redact_arguments(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return deepcopy(value)


def redact_text(value: str) -> str:
    redacted = value
    for pattern in SECRET_TEXT_PATTERNS:
        redacted = pattern.sub(_mask_secret_match, redacted)
    return redacted


def validate_approval_mode(value: str) -> ApprovalMode:
    if value not in VALID_APPROVAL_MODES:
        raise ValueError(f"Invalid approval mode: {value}")
    return value  # type: ignore[return-value]


def _find_pending_approval(
    db: Session,
    user: CurrentUser,
    conversation_id: str,
    tool_name: str,
    approval_id: str | None,
    *,
    fail_on_expired: bool = True,
) -> AssistantApproval | None:
    now = _now()
    if approval_id:
        approval = db.get(AssistantApproval, approval_id)
        if (
            approval is not None
            and approval.user_id == user.id
            and approval.conversation_id == conversation_id
            and approval.status == "pending"
        ):
            if approval.expires_at <= now:
                _expire_approval(db, approval)
                if fail_on_expired:
                    raise ValueError("审批已过期或不可用，请重新发起操作。")
                return None
            return approval
        return None

    stmt = (
        select(AssistantApproval)
        .where(AssistantApproval.user_id == user.id)
        .where(AssistantApproval.conversation_id == conversation_id)
        .where(AssistantApproval.tool_name == tool_name)
        .where(AssistantApproval.status == "pending")
        .order_by(AssistantApproval.created_at.desc())
        .limit(1)
    )
    approval = db.scalars(stmt).first()
    if approval is not None and approval.expires_at <= now:
        _expire_approval(db, approval)
        if fail_on_expired:
            raise ValueError("审批已过期或不可用，请重新发起操作。")
        return None
    return approval


def _redacted_payload(payload: dict[str, Any]) -> dict[str, Any]:
    redacted = redact_arguments(payload)
    if isinstance(redacted, dict) and isinstance(redacted.get("arguments"), dict):
        redacted["arguments"] = redact_arguments(redacted["arguments"])
    return redacted


def _risk_level(tool_name: str) -> str:
    policy = get_tool_policy(tool_name)
    return policy.risk_level if policy is not None else "destructive"


def _org_id(user: CurrentUser) -> str:
    if not user.org_id:
        raise ValueError("Assistant action audit requires user organization context")
    return user.org_id


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _is_sensitive_key(key: str) -> bool:
    return key.lower() in SENSITIVE_ARGUMENT_KEYS


def _expire_approval(db: Session, approval: AssistantApproval) -> None:
    now = _now()
    approval.status = "expired"
    approval.resolved_at = now
    audit = db.get(AssistantActionAudit, approval.action_audit_id)
    if audit is not None and audit.status == "pending_approval":
        audit.status = "expired"
        audit.completed_at = now
    db.commit()


def _mask_secret_match(match: re.Match[str]) -> str:
    text = match.group(0)
    if text.lower().startswith("bearer "):
        return "Bearer ***redacted***"
    if text.startswith("sk-"):
        return "sk-***redacted***"
    separator = "=" if "=" in text else ":"
    key = text.split(separator, 1)[0].strip()
    return f"{key}{separator}***redacted***"
