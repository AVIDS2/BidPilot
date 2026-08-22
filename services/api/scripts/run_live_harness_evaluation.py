# ruff: noqa: E402
"""Run a real, trace-backed evaluation against the configured assistant model.

This is intentionally separate from pytest: the normal test configuration
clears provider credentials and replaces the model with deterministic doubles.
The script creates an isolated workspace, exercises the public Harness adapter
with the configured server-side model, and writes a redacted trace report.

Usage (from ``services/api``)::

    uv run python scripts/run_live_harness_evaluation.py --execute

The evaluation records remain in the database on purpose. They are labelled
``live-harness-eval`` so that operators can inspect the same RuntimeRun,
RuntimeEvent, RuntimeAction and RuntimeApproval records rendered by the UI.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.runtime.model import resolve_agent_model
from app.auth.schemas import CurrentUser
from app.db import SessionLocal
from app.models import (
    Bundle,
    Organization,
    OrganizationMembership,
    Project,
    ProjectMember,
    RuntimeAction,
    RuntimeApproval,
    RuntimeEvent,
    RuntimeRun,
    SourceDocument,
    User,
)
from app.assistant.schemas import AssistantConfirmation, AssistantRequest
from app.retrieval.embedding import generate_query_embedding, get_embedding_profile
from app.runtime.operator_adapter import stream_operator_assistant_response
from app.usage.schemas import ProviderSource


_SSE_EVENT = re.compile(r"^event: (?P<name>[^\n]+)$", re.MULTILINE)
_SSE_DATA = re.compile(r"^data: (?P<data>.+)$", re.MULTILINE)
_MAX_PUBLIC_TEXT = 1_200
_PUBLIC_UUID = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.IGNORECASE)
_INTERNAL_REPLY_MARKERS = (
    "active_project_id",
    "runtime_run_id",
    "short_id",
    "list_deliverables",
    "list_requirements",
    "get_project_outline",
    "list_sections",
    "start_draft_section",
    "create_deliverable",
    "export_deliverable",
)


@dataclass(frozen=True)
class EvaluationContext:
    user: CurrentUser
    project_id: str
    label: str


def _parse_sse(frame: str) -> tuple[str | None, dict[str, Any]]:
    event = _SSE_EVENT.search(frame)
    data = _SSE_DATA.search(frame)
    if event is None or data is None:
        return None, {}
    try:
        decoded = json.loads(data.group("data"))
    except json.JSONDecodeError:
        decoded = {}
    return event.group("name"), decoded if isinstance(decoded, dict) else {}


def _safe_text(value: Any, *, limit: int = _MAX_PUBLIC_TEXT) -> str:
    return str(value or "").replace("\r", "").strip()[:limit]


def _create_context(db: Session) -> EvaluationContext:
    suffix = uuid4().hex[:10]
    label = f"live-harness-eval-{suffix}"
    org = Organization(slug=label, name=f"真实 Harness 验收 {suffix}")
    db.add(org)
    db.flush()
    user = User(
        org_id=org.id,
        email=f"{label}@bidpilot.local",
        display_name="Harness Live Evaluation",
        password_hash="evaluation-only-no-login",
        role="admin",
        email_verified=True,
    )
    db.add(user)
    db.flush()
    project = Project(
        org_id=org.id,
        slug=f"{label}-project",
        name="真实验收投标项目",
        scenario_package="bidpilot",
    )
    db.add(project)
    db.flush()
    bundle = Bundle(
        project_id=project.id,
        label="真实验收资料包",
        source_type="evaluation",
        ingest_status="completed",
    )
    db.add_all(
        [
            OrganizationMembership(org_id=org.id, user_id=user.id, role="owner", status="active"),
            ProjectMember(project_id=project.id, user_id=user.id, role="owner"),
            bundle,
        ]
    )
    db.flush()
    db.add(
        SourceDocument(
            bundle_id=bundle.id,
            storage_key=f"evaluations/{label}/technical-requirements.txt",
            mime_type="text/plain",
            checksum="evaluation-only-technical-requirements",
            original_filename="技术需求摘要.txt",
            parse_status="completed",
            index_status="completed",
        )
    )
    db.commit()
    return EvaluationContext(
        user=CurrentUser(
            id=user.id,
            email=user.email,
            display_name=user.display_name,
            role=user.role,
            plan="starter",
            email_verified=True,
            disabled=False,
            org_id=org.id,
            org_slug=org.slug,
        ),
        project_id=project.id,
        label=label,
    )


async def _run_turn(
    db: Session,
    context: EvaluationContext,
    *,
    name: str,
    message: str,
    conversation_id: str | None = None,
    approval_mode: str = "risky_only",
    confirmation: AssistantConfirmation | None = None,
) -> tuple[dict[str, Any], str | None]:
    resolved = resolve_agent_model()
    payload = AssistantRequest(
        message=message,
        client_request_id=f"{context.label}-{name}-{uuid4().hex[:12]}",
        project_id=context.project_id,
        conversation_id=conversation_id,
        approval_mode=approval_mode,  # type: ignore[arg-type]
        reasoning_effort="low",
        confirmation=confirmation,
    )
    frames: list[tuple[str, dict[str, Any]]] = []
    async for frame in stream_operator_assistant_response(
        db,
        context.user,
        payload,
        provider_type=resolved.provider_type,
        provider_id=resolved.provider_id,
        provider_source=ProviderSource.OFFICIAL,
        api_key=resolved.api_key,
        base_url=resolved.base_url,
        model=resolved.model,
    ):
        event, data = _parse_sse(frame)
        if event:
            frames.append((event, data))

    start = next((data for event, data in frames if event == "assistant.start"), {})
    runtime_run_id = start.get("runtime_run_id")
    active_conversation_id = start.get("conversation_id") or conversation_id
    run = db.get(RuntimeRun, runtime_run_id) if isinstance(runtime_run_id, str) else None
    events = (
        list(
            db.scalars(
                select(RuntimeEvent)
                .where(RuntimeEvent.run_id == runtime_run_id)
                .order_by(RuntimeEvent.sequence)
            )
        )
        if isinstance(runtime_run_id, str)
        else []
    )
    actions = (
        list(
            db.scalars(
                select(RuntimeAction)
                .where(RuntimeAction.run_id == runtime_run_id)
                .order_by(RuntimeAction.created_at)
            )
        )
        if isinstance(runtime_run_id, str)
        else []
    )
    approval = (
        db.scalar(
            select(RuntimeApproval)
            .join(RuntimeAction, RuntimeApproval.action_id == RuntimeAction.id)
            .where(RuntimeAction.run_id == runtime_run_id)
            .order_by(RuntimeApproval.created_at.desc())
        )
        if isinstance(runtime_run_id, str)
        else None
    )
    visible_reply = "".join(
        _safe_text(data.get("content"), limit=4_000)
        for event, data in frames
        if event == "assistant.message"
    )
    return (
        {
            "name": name,
            "request": message,
            "runtime_run_id": runtime_run_id,
            "trace_id": run.trace_id if run is not None else None,
            "run_status": run.status if run is not None else "missing",
            "error_code": run.error_code if run is not None else None,
            "reply": _safe_text(visible_reply),
            "sse_event_types": [event for event, _data in frames],
            "runtime_events": [
                {
                    "sequence": event.sequence,
                    "type": event.event_type,
                    "summary": _safe_text(event.public_summary, limit=300),
                }
                for event in events
            ],
            "actions": [
                {
                    "capability": action.capability_name,
                    "status": action.status,
                    "risk": action.risk_level,
                    "policy": action.policy_outcome,
                    "error_code": action.error_code,
                    "summary": _safe_text(action.public_summary, limit=300),
                }
                for action in actions
            ],
            "approval": (
                {
                    "id": approval.id,
                    "status": approval.status,
                    "action_id": approval.action_id,
                }
                if approval is not None
                else None
            ),
        },
        active_conversation_id if isinstance(active_conversation_id, str) else None,
    )


async def _execute(output_dir: Path) -> tuple[Path, bool]:
    output_dir.mkdir(parents=True, exist_ok=True)
    db = SessionLocal()
    try:
        context = _create_context(db)
        results: list[dict[str, Any]] = []

        answer, conversation_id = await _run_turn(
            db,
            context,
            name="general_answer",
            message="不用调用工具，用一句话解释投标响应中的需求追溯是什么。",
            approval_mode="full_access",
        )
        results.append(answer)

        inspection, conversation_id = await _run_turn(
            db,
            context,
            name="project_material_inspection",
            conversation_id=conversation_id,
            message=(
                "请读取当前项目的资料包和文档，说明有哪些可用于技术方案的材料。"
                "只查询，不要修改任何数据。"
            ),
            approval_mode="risky_only",
        )
        results.append(inspection)

        write, conversation_id = await _run_turn(
            db,
            context,
            name="create_deliverable",
            conversation_id=conversation_id,
            message="请在当前项目创建一个名为“真实验收交付物”的投标响应文档，直接执行。",
            approval_mode="full_access",
        )
        results.append(write)

        readiness, conversation_id = await _run_turn(
            db,
            context,
            name="readiness_analysis",
            conversation_id=conversation_id,
            message=(
                "查询当前项目的投标准备度、已有资料、章节和待处理缺口，"
                "给出三条下一步建议。只查询，不要修改。"
            ),
            approval_mode="risky_only",
        )
        results.append(readiness)

        approval_request, approval_conversation_id = await _run_turn(
            db,
            context,
            name="approval_request",
            message=(
                "创建一个名为“真实验收审批项目”的投标项目，信息已经完整，请直接发起创建动作。"
                "平台会按当前权限策略处理需要的审批。"
            ),
            approval_mode="risky_only",
        )
        results.append(approval_request)
        approval_payload = approval_request.get("approval") or {}
        if approval_payload.get("id") and approval_conversation_id:
            action = db.get(RuntimeAction, approval_payload.get("action_id"))
            if action is not None:
                approval_resume, _ = await _run_turn(
                    db,
                    context,
                    name="approval_resume",
                    conversation_id=approval_conversation_id,
                    message="确认执行",
                    approval_mode="risky_only",
                    confirmation=AssistantConfirmation(
                        approved=True,
                        tool_name=action.capability_name,
                        arguments=action.arguments_json or {},
                        approval_id=str(approval_payload["id"]),
                    ),
                )
                results.append(approval_resume)

        embedding_profile = get_embedding_profile()
        embedding = generate_query_embedding("投标技术方案需求追溯", timeout_seconds=30.0)
        payload = {
            "executed_at": datetime.now(UTC).isoformat(),
            "workspace_label": context.label,
            "project_id": context.project_id,
            "provider": {
                "id": resolve_agent_model().provider_id,
                "model": resolve_agent_model().model,
            },
            "embedding": {
                "configured": embedding_profile is not None,
                "profile": embedding.profile_id,
                "status": embedding.status.value,
                "error_code": embedding.error_code,
                "dimensions": len(embedding.vector or []),
                "token_count": embedding.token_count,
            },
            "scenarios": results,
        }
        payload["acceptance"] = _evaluate_acceptance(payload)
        report_json = output_dir / f"{context.label}.json"
        report_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        report_md = output_dir / f"{context.label}.md"
        report_md.write_text(_markdown_report(payload), encoding="utf-8")
        return report_md, bool(payload["acceptance"]["passed"])
    finally:
        db.close()


def _markdown_report(payload: dict[str, Any]) -> str:
    lines = [
        "# 真实 Harness 验收报告",
        "",
        f"- 执行时间：{payload['executed_at']}",
        f"- 隔离工作区：`{payload['workspace_label']}`",
        f"- 模型：`{payload['provider']['id']} / {payload['provider']['model']}`",
        (
            "- 向量请求："
            f"`{payload['embedding']['status']}`，维度 `{payload['embedding']['dimensions']}`"
            + (f"，错误 `{payload['embedding']['error_code']}`" if payload['embedding']['error_code'] else "")
        ),
        "",
        "## 验收结论",
        "",
        f"- 状态：`{'passed' if payload['acceptance']['passed'] else 'failed'}`",
    ]
    failures = payload["acceptance"].get("failures") or []
    if failures:
        lines.extend([f"- 未通过：{failure}" for failure in failures])
    lines.extend(
        [
            "",
        "## 场景结果",
        "",
        ]
    )
    for scenario in payload["scenarios"]:
        action_text = ", ".join(
            f"`{item['capability']}` ({item['status']})" for item in scenario["actions"]
        ) or "无"
        lines.extend(
            [
                f"### {scenario['name']}",
                "",
                f"- 运行：`{scenario['runtime_run_id']}` / `{scenario['run_status']}`",
                f"- Trace：`{scenario['trace_id']}`",
                f"- 工具：{action_text}",
                f"- 回复：{scenario['reply'] or '（无可见文本）'}",
                "",
            ]
        )
    return "\n".join(lines)


def _evaluate_acceptance(payload: dict[str, Any]) -> dict[str, Any]:
    """Turn a live trace into an explicit pass/fail gate, not a prose report."""
    scenarios = {
        str(item.get("name")): item
        for item in payload.get("scenarios") or []
        if isinstance(item, dict) and item.get("name")
    }
    failures: list[str] = []

    def require(name: str, *, status: str = "succeeded", capability: str | None = None) -> None:
        item = scenarios.get(name)
        if item is None:
            failures.append(f"缺少场景 {name}")
            return
        if item.get("run_status") != status:
            failures.append(f"{name} 运行状态为 {item.get('run_status')!r}，期望 {status!r}")
        if item.get("error_code"):
            failures.append(f"{name} 返回错误码 {item['error_code']!r}")
        if capability and not any(
            action.get("capability") == capability and action.get("status") == "succeeded"
            for action in item.get("actions") or []
            if isinstance(action, dict)
        ):
            failures.append(f"{name} 未留下成功的 {capability} 动作")

    require("general_answer")
    require("project_material_inspection")
    require("create_deliverable", capability="create_deliverable")
    require("readiness_analysis")
    require("approval_resume", capability="create_project")

    write = scenarios.get("create_deliverable")
    if write is not None:
        successful_writes = [
            action
            for action in write.get("actions") or []
            if isinstance(action, dict)
            and action.get("capability") == "create_deliverable"
            and action.get("status") == "succeeded"
        ]
        if len(successful_writes) != 1:
            failures.append(
                "create_deliverable 成功写入次数为 "
                f"{len(successful_writes)}，期望恰好 1 次（不得因模型重试重复创建）"
            )

    approval = scenarios.get("approval_request")
    if approval is None:
        failures.append("缺少场景 approval_request")
    else:
        if approval.get("run_status") != "awaiting_approval":
            failures.append(f"approval_request 运行状态为 {approval.get('run_status')!r}，期望 'awaiting_approval'")
        approval_record = approval.get("approval") or {}
        if approval_record.get("status") not in {"pending", "approved", "edited"}:
            failures.append("approval_request 未创建 RuntimeApproval")
        if not any(
            action.get("capability") == "create_project" and action.get("status") == "awaiting_approval"
            for action in approval.get("actions") or []
            if isinstance(action, dict)
        ):
            failures.append("approval_request 未留下 awaiting_approval 的 create_project 动作")

    embedding = payload.get("embedding") or {}
    if embedding.get("status") != "success" or int(embedding.get("dimensions") or 0) <= 0:
        failures.append("向量模型调用未成功产生向量")

    for scenario in scenarios.values():
        reply = str(scenario.get("reply") or "")
        normalized_reply = reply.lower()
        if _PUBLIC_UUID.search(reply) or any(marker in normalized_reply for marker in _INTERNAL_REPLY_MARKERS):
            failures.append(f"{scenario.get('name')} 向用户泄漏了内部标识符或工具名")

    return {"passed": not failures, "failures": failures}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run real model Harness evaluation")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Required acknowledgement: this sends real model and embedding requests.",
    )
    parser.add_argument(
        "--output-dir",
        default="artifacts/evaluations/live-harness",
        help="Directory for redacted JSON/Markdown reports.",
    )
    args = parser.parse_args()
    if not args.execute:
        parser.error("Refusing to call live providers without --execute")
    report, passed = asyncio.run(_execute(Path(args.output_dir)))
    print(report.resolve())
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
