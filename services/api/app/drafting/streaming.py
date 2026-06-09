"""SSE streaming support for BidPilot agent graph execution.

Provides an async generator ``stream_graph_events`` that the router
consumes via ``sse_starlette.EventSourceResponse``.

Polling strategy:
1. **Primary**: query the LangGraph ``checkpoints`` / ``checkpoint_writes``
   tables directly to detect node transitions in real time.
2. **Fallback**: poll the ``ExecutionRun`` status column when the
   checkpoint tables are unavailable (e.g. non-LangGraph runs).
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import ExecutionRun

logger = logging.getLogger(__name__)

# ── Graph node names in execution order (for fallback sequencing) ────────
_GRAPH_NODE_ORDER = [
    "supervisor",
    "rfp_parser",
    "knowledge_retriever",
    "section_drafter",
    "quality_reviewer",
    "human_approval",
    "persist_result",
]

# Terminal statuses that stop the stream
_TERMINAL_STATUSES = frozenset({"succeeded", "failed", "cancelled", "error"})

# Polling interval in seconds
_POLL_INTERVAL = 1.5

# Maximum stream duration (5 minutes)
_MAX_STREAM_SECONDS = 300


def _sse_event(event: str, data: dict[str, Any]) -> dict[str, str]:
    """Return an SSE-compatible dict for ``EventSourceResponse``."""
    return {"event": event, "data": json.dumps(data, default=str)}


# ── Checkpoint-based polling ─────────────────────────────────────────────

def _try_read_latest_checkpoint(
    db: Session,
    thread_id: str,
) -> dict[str, Any] | None:
    """Read the latest checkpoint metadata for a thread from LangGraph tables.

    Returns a dict with ``node_name``, ``checkpoint_id``, ``metadata``,
    and ``state`` (the checkpoint payload) or ``None`` if the tables
    don't exist or the thread has no checkpoints.
    """
    try:
        result = db.execute(
            text(
                """
                SELECT checkpoint_id, parent_checkpoint_id, type, checkpoint, metadata
                FROM checkpoints
                WHERE thread_id = :thread_id AND checkpoint_ns = ''
                ORDER BY checkpoint_id DESC
                LIMIT 1
                """
            ),
            {"thread_id": thread_id},
        )
        row = result.mappings().first()
        if row is None:
            return None

        checkpoint = row["checkpoint"]
        metadata = row["metadata"] or {}

        # LangGraph stores state as {"v": 1, "id": ..., "ts": ..., "channel_values": {...}, ...}
        state: dict[str, Any] = {}
        if isinstance(checkpoint, dict):
            state = checkpoint.get("channel_values", checkpoint.get("state", {}))

        node_name = _detect_current_node(db, thread_id, row["checkpoint_id"])

        return {
            "node_name": node_name,
            "checkpoint_id": row["checkpoint_id"],
            "parent_checkpoint_id": row["parent_checkpoint_id"],
            "metadata": metadata,
            "state": state,
        }
    except Exception as exc:
        logger.debug("Checkpoint read failed (expected for non-LangGraph runs): %s", exc)
        return None


def _detect_current_node(
    db: Session,
    thread_id: str,
    checkpoint_id: str,
) -> str:
    """Determine which graph node produced the given checkpoint.

    Examines ``checkpoint_writes`` for write channels matching known node
    names.  Falls back to the metadata ``step`` / ``node`` fields.
    """
    try:
        result = db.execute(
            text(
                """
                SELECT DISTINCT channel, type
                FROM checkpoint_writes
                WHERE thread_id = :thread_id
                  AND checkpoint_ns = ''
                  AND checkpoint_id = :checkpoint_id
                """
            ),
            {"thread_id": thread_id, "checkpoint_id": checkpoint_id},
        )
        rows = result.mappings().all()

        known_nodes = set(_GRAPH_NODE_ORDER)
        for row in rows:
            channel = row.get("channel", "")
            if channel in known_nodes:
                return channel

        # Fallback: metadata
        meta_result = db.execute(
            text(
                "SELECT metadata FROM checkpoints "
                "WHERE thread_id = :tid AND checkpoint_id = :cid AND checkpoint_ns = ''"
            ),
            {"tid": thread_id, "cid": checkpoint_id},
        )
        meta_row = meta_result.mappings().first()
        if meta_row:
            meta = meta_row.get("metadata") or {}
            if "node" in meta:
                return meta["node"]
            if "step" in meta:
                step = meta["step"]
                if isinstance(step, int) and 0 <= step < len(_GRAPH_NODE_ORDER):
                    return _GRAPH_NODE_ORDER[step]

        return "unknown"
    except Exception:
        return "unknown"


def _extract_review_result(state: dict[str, Any]) -> dict[str, Any] | None:
    """Extract review_result from checkpoint state if available."""
    review = state.get("review_result")
    if review and isinstance(review, dict):
        return {
            "passed": review.get("passed", False),
            "issues": review.get("issues", []),
            "score": review.get("overall_score", 0.0),
        }
    return None


def _build_node_summary(node_name: str, state: dict[str, Any]) -> str:
    """Build a human-readable summary of a completed node's output."""
    if node_name == "rfp_parser":
        count = len(state.get("requirements", []))
        return f"Parsed {count} requirement(s)"
    if node_name == "knowledge_retriever":
        count = len(state.get("evidence_chunks", []))
        return f"Retrieved {count} evidence chunk(s)"
    if node_name == "section_drafter":
        model = state.get("draft_model_used", "unknown")
        created = state.get("draft_created", False)
        return f"Draft {'created' if created else 'failed'} via {model}"
    if node_name == "quality_reviewer":
        review = state.get("review_result", {})
        passed = review.get("passed", False) if isinstance(review, dict) else False
        score = review.get("overall_score", 0.0) if isinstance(review, dict) else 0.0
        return f"Review {'passed' if passed else 'failed'} (score: {score:.2f})"
    if node_name == "human_approval":
        decision = state.get("human_decision", "pending")
        return f"Human decision: {decision}"
    if node_name == "persist_result":
        persisted = state.get("persisted", False)
        return f"Result {'persisted' if persisted else 'persistence failed'}"
    return f"Node {node_name} completed"


# ── Main streaming generator ─────────────────────────────────────────────

async def stream_graph_events(run_id: str, db: Session):
    """Async generator yielding SSE event dicts for a graph execution run.

    Designed for use with ``sse_starlette.EventSourceResponse``::

        return EventSourceResponse(stream_graph_events(run_id, db))

    Yields dicts with ``event`` and ``data`` keys (string values).
    """
    # Verify the run exists
    run = db.get(ExecutionRun, run_id)
    if run is None:
        yield _sse_event("graph_error", {"error_message": f"Run {run_id} not found"})
        return

    yield _sse_event("connected", {
        "run_id": run_id,
        "status": run.status,
        "timestamp": datetime.now(UTC).isoformat(),
    })

    # Already terminal -- emit and return
    if run.status in _TERMINAL_STATUSES:
        output = run.output_json or {}
        yield _sse_event("graph_completed", {
            "persisted": run.status == "succeeded",
            "section_version_id": output.get("section_version_id"),
            "status": run.status,
            "timestamp": datetime.now(UTC).isoformat(),
        })
        return

    thread_id = run_id  # LangGraph thread_id == run_id by convention
    seen_checkpoint_ids: set[str] = set()
    seen_node_completions: set[str] = set()
    use_checkpoint_polling = True
    elapsed = 0.0

    while elapsed < _MAX_STREAM_SECONDS:
        await asyncio.sleep(_POLL_INTERVAL)
        elapsed += _POLL_INTERVAL

        # Refresh run from DB
        db.expire_all()
        run = db.get(ExecutionRun, run_id)
        if run is None:
            yield _sse_event("graph_error", {"error_message": "Run record disappeared"})
            return

        # ── Checkpoint-based polling ────────────────────────────────────
        if use_checkpoint_polling:
            checkpoint = _try_read_latest_checkpoint(db, thread_id)

            if checkpoint is None and not seen_checkpoint_ids:
                # Tables don't exist -- switch to fallback on first miss
                logger.debug(
                    "Checkpoint tables unavailable for run %s -- falling back to ExecutionRun polling",
                    run_id,
                )
                use_checkpoint_polling = False

            elif checkpoint is not None:
                cp_id = checkpoint["checkpoint_id"]

                if cp_id not in seen_checkpoint_ids:
                    seen_checkpoint_ids.add(cp_id)
                    node_name = checkpoint["node_name"]
                    state = checkpoint["state"]

                    yield _sse_event("node_started", {
                        "node_name": node_name,
                        "timestamp": datetime.now(UTC).isoformat(),
                    })

                    if node_name not in seen_node_completions:
                        seen_node_completions.add(node_name)
                        yield _sse_event("node_completed", {
                            "node_name": node_name,
                            "result_summary": _build_node_summary(node_name, state),
                            "timestamp": datetime.now(UTC).isoformat(),
                        })

                    if node_name == "quality_reviewer":
                        review = _extract_review_result(state)
                        if review:
                            yield _sse_event("review_result", review)

                    if node_name == "human_approval":
                        draft_preview = state.get("draft_markdown", "")[:2000]
                        review_data = state.get("review_result")
                        yield _sse_event("human_approval_required", {
                            "draft_preview": draft_preview,
                            "review_score": (
                                review_data.get("overall_score")
                                if isinstance(review_data, dict)
                                else None
                            ),
                            "timestamp": datetime.now(UTC).isoformat(),
                        })

                    error = state.get("error")
                    if error:
                        yield _sse_event("graph_error", {
                            "error_message": str(error),
                            "timestamp": datetime.now(UTC).isoformat(),
                        })
                        return

        # ── Fallback: ExecutionRun status polling ───────────────────────
        if not use_checkpoint_polling:
            yield _sse_event("heartbeat", {
                "run_id": run_id,
                "status": run.status,
                "elapsed_seconds": round(elapsed, 1),
                "timestamp": datetime.now(UTC).isoformat(),
            })

        # ── Terminal check (both strategies) ────────────────────────────
        if run.status in _TERMINAL_STATUSES:
            output = run.output_json or {}
            yield _sse_event("graph_completed", {
                "persisted": run.status == "succeeded",
                "section_version_id": output.get("section_version_id"),
                "status": run.status,
                "timestamp": datetime.now(UTC).isoformat(),
            })
            return

    # Timeout
    yield _sse_event("graph_error", {
        "error_message": f"Stream timed out after {_MAX_STREAM_SECONDS}s",
        "timestamp": datetime.now(UTC).isoformat(),
    })
