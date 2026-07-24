#!/usr/bin/env python3
"""BidPilot internal MCP server.

Exposes governed capabilities over MCP stdio. Every mutation still goes through
execute_capability (approval / quota / tenant / audit).

Auth:
  DOCPILOT_MCP_TOKEN       — user JWT access token (preferred)
  DOCPILOT_MCP_USER_EMAIL  — trusted local operator email fallback

Usage:
  DOCPILOT_MCP_TOKEN=... python scripts/bidpilot_mcp.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [
    str(ROOT / "services" / "api"),
    str(ROOT / "packages"),
]

from mcp.server.fastmcp import FastMCP
from sqlalchemy import select

from app.auth.schemas import CurrentUser
from app.auth.service import _user_to_current, get_current_user_from_token
from app.db import SessionLocal
from app.models import User
from app.runtime.registry import CAPABILITY_REGISTRY, missing_required_capability_arguments
from app.runtime.service import create_runtime_run, execute_capability

mcp = FastMCP(
    "bidpilot",
    instructions=(
        "BidPilot governed platform tools. Prefer outline-first drafting, "
        "use id/short_id for same-name projects, and never bypass approvals."
    ),
)


def _load_user(db) -> CurrentUser:
    token = (os.environ.get("DOCPILOT_MCP_TOKEN") or "").strip()
    email = (os.environ.get("DOCPILOT_MCP_USER_EMAIL") or "").strip()
    if token:
        current = get_current_user_from_token(db, token)
        if current is None:
            raise RuntimeError("DOCPILOT_MCP_TOKEN is invalid")
        return current
    if email:
        user = db.scalar(select(User).where(User.email == email).limit(1))
        if user is None:
            raise RuntimeError(f"DOCPILOT_MCP_USER_EMAIL not found: {email}")
        return _user_to_current(db, user)
    raise RuntimeError("Set DOCPILOT_MCP_TOKEN or DOCPILOT_MCP_USER_EMAIL")


def _run_capability(name: str, arguments: dict[str, Any]) -> str:
    missing = missing_required_capability_arguments(name, arguments)
    if missing:
        return json.dumps(
            {
                "error": f"missing required fields: {', '.join(missing)}",
                "missing_fields": list(missing),
            },
            ensure_ascii=False,
        )
    db = SessionLocal()
    try:
        user = _load_user(db)
        project_id = arguments.get("project_id")
        run = create_runtime_run(
            db,
            user,
            kind="mcp_tool",
            engine="mcp",
            project_id=project_id if isinstance(project_id, str) else None,
            approval_mode=os.environ.get("DOCPILOT_MCP_APPROVAL_MODE", "risky_only"),
            input_json={"capability": name, "arguments": arguments, "source": "mcp"},
        )
        execution = execute_capability(
            db,
            user,
            run_id=run.id,
            capability_name=name,
            arguments=arguments,
            action_key=f"mcp:{run.id}:{name}",
        )
        if execution.approval is not None:
            payload = (
                execution.approval.payload_json
                if isinstance(execution.approval.payload_json, dict)
                else {}
            )
            return json.dumps(
                {
                    "status": "needs_confirmation",
                    "approval_id": execution.approval.id,
                    "message": payload.get("message"),
                    "expected_text": payload.get("expected_text"),
                    "arguments": payload.get("arguments") or arguments,
                },
                ensure_ascii=False,
            )
        result = execution.result
        return json.dumps(
            {
                "status": execution.action.status,
                "summary": result.summary if result else None,
                "payload": result.payload if result else {},
                "error": execution.action.error_message,
            },
            ensure_ascii=False,
        )
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False)
    finally:
        db.close()


@mcp.tool(name="list_capabilities", description="List BidPilot governed capabilities available via MCP")
def list_capabilities() -> str:
    items = [
        {
            "name": item.name,
            "label_zh": item.label_zh,
            "label_en": item.label_en,
            "risk_level": str(item.risk_level),
            "required_scope": getattr(item, "required_scope", None),
        }
        for item in sorted(CAPABILITY_REGISTRY.values(), key=lambda value: value.name)
    ]
    return json.dumps({"count": len(items), "items": items}, ensure_ascii=False)


@mcp.tool(
    name="invoke_capability",
    description=(
        "Invoke a BidPilot capability by name. Pass arguments as a JSON object. "
        "Destructive/costing tools may return needs_confirmation."
    ),
)
def invoke_capability(name: str, arguments_json: str = "{}") -> str:
    try:
        arguments = json.loads(arguments_json) if arguments_json else {}
        if not isinstance(arguments, dict):
            raise ValueError("arguments_json must decode to an object")
    except Exception as exc:  # noqa: BLE001
        return json.dumps({"status": "failed", "error": f"invalid arguments_json: {exc}"}, ensure_ascii=False)
    if name not in CAPABILITY_REGISTRY:
        return json.dumps({"status": "failed", "error": f"unknown capability: {name}"}, ensure_ascii=False)
    return _run_capability(name, arguments)


if __name__ == "__main__":
    mcp.run(transport="stdio")
