"""Load a bounded, authorized governed-memory pack for one workflow run."""

from __future__ import annotations

import logging
import time

from sqlalchemy import select

from app.db import SessionLocal
from app.execution.embedding_capacity import generate_metered_embedding
from app.models import Project, ProjectMember, RuntimeRun, User
from contracts.access import project_role_has_capability
from contracts.memory_service import build_memory_context_pack

from ..state import BidPilotState, MemoryContextEntry
from ._history import record_agent_call


logger = logging.getLogger(__name__)
_TOP_K = 8
_MAX_CHARACTERS = 8_000


def _memory_query(state: BidPilotState) -> str:
    requirements = state.get("requirements", [])[:3]
    requirement_text = " ".join(
        str(item.get("requirement_text") or "")[:300]
        for item in requirements
        if isinstance(item, dict)
    )
    return f"{state.get('section_key', '').replace('-', ' ')} {requirement_text}".strip()


def _degraded_result(reason: str, *, started: float, success: bool = True) -> dict:
    history = record_agent_call(
        agent="memory_context",
        action="load_governed_memory",
        input_summary="runtime principal unavailable",
        output_summary=f"memory_context=0, degraded={reason}",
        duration_ms=int((time.monotonic() - started) * 1000),
        success=success,
        error=None if success else reason,
    )
    return {
        "memory_context_loaded": True,
        "memory_context_items": [],
        "memory_context_version": None,
        "memory_context_degraded_reasons": [reason],
        "agent_history": history,
    }


def load_memory_context_node(state: BidPilotState) -> dict:
    """Load only the initiating user's authorized memory before drafting.

    A workflow without a trusted RuntimeRun principal intentionally receives no
    private memory. Retrieval degradation is explicit and never blocks raw
    evidence retrieval or fabricates a vector.
    """
    started = time.monotonic()
    runtime_run_id = state.get("runtime_run_id")
    if not runtime_run_id:
        return _degraded_result("missing_runtime_principal", started=started)

    db = SessionLocal()
    try:
        runtime_run = db.get(RuntimeRun, runtime_run_id)
        project = db.get(Project, state.get("project_id"))
        if (
            runtime_run is None
            or project is None
            or runtime_run.project_id != project.id
            or runtime_run.org_id != project.org_id
        ):
            return _degraded_result("invalid_runtime_principal", started=started)
        user = db.get(User, runtime_run.user_id)
        if user is None or user.org_id != project.org_id or user.disabled:
            return _degraded_result("invalid_runtime_principal", started=started)
        if user.role != "admin":
            membership = db.scalar(
                select(ProjectMember).where(
                    ProjectMember.project_id == project.id,
                    ProjectMember.user_id == user.id,
                )
            )
            if membership is None or not project_role_has_capability(membership.role, "memory.read"):
                return _degraded_result("runtime_principal_memory_access_revoked", started=started)

        query = _memory_query(state)
        embedding = generate_metered_embedding(
            db,
            org_id=project.org_id,
            user_id=user.id,
            project_id=project.id,
            workload="embedding_workflow_memory_query",
            text=query,
            execution_run_id=state.get("run_id"),
            runtime_run_id=runtime_run.id,
        )
        pack = build_memory_context_pack(
            db,
            org_id=project.org_id,
            user_id=user.id,
            project_id=project.id,
            raw_query=query,
            profile_id=embedding.profile_id if embedding.is_success else None,
            query_embedding=embedding.embedding if embedding.is_success else None,
            top_k=_TOP_K,
            max_characters=_MAX_CHARACTERS,
            include_user_private=user.memory_enabled,
        )
        items: list[MemoryContextEntry] = [
            MemoryContextEntry(
                title=item.title,
                body_markdown=item.body_markdown,
                scope=item.scope.value,
                kind=item.kind.value,
                citations=[citation.label for citation in item.citations],
            )
            for item in pack.items
        ]
        history = record_agent_call(
            agent="memory_context",
            action="load_governed_memory",
            input_summary=f"project={project.id}, section={state.get('section_key', '')}",
            output_summary=(
                f"memory_context={len(items)}, version={pack.memory_version[:12]}, "
                f"degraded={','.join(pack.degraded_reasons) or 'none'}"
            ),
            duration_ms=int((time.monotonic() - started) * 1000),
            success=True,
        )
        return {
            "memory_context_loaded": True,
            "memory_context_items": items,
            "memory_context_version": pack.memory_version,
            "memory_context_degraded_reasons": list(pack.degraded_reasons),
            "agent_history": history,
        }
    except Exception:
        logger.exception("Governed memory context loading failed")
        return _degraded_result("memory_context_unavailable", started=started, success=False)
    finally:
        db.close()
