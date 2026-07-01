"""BidPilot LangGraph state definition.

Central TypedDict shared by every node in the drafting graph.
Each node receives the full state and returns a partial update.
"""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from langgraph.graph import add_messages


class AgentCall(TypedDict):
    """Record of a single agent node invocation for observability."""

    agent: str
    action: str
    input_summary: str
    output_summary: str
    duration_ms: int
    success: bool
    error: str | None


class EvidenceChunk(TypedDict):
    """A single retrieved knowledge chunk with its similarity score."""

    chunk_id: str
    source_document_id: str
    content: str
    cosine_distance: float
    chunk_index: int


class Requirement(TypedDict):
    """A single extracted requirement from the RFP."""

    section_key: str
    requirement_text: str
    priority: str  # "high" | "normal" | "low"


class ReviewResult(TypedDict):
    """Structured output from the quality reviewer."""

    passed: bool
    issues: list[str]
    suggestions: list[str]
    overall_score: float


class BidPilotState(TypedDict):
    """Shared state for the BidPilot LangGraph agent.

    Fields are populated progressively as the graph traverses nodes.
    All fields are optional at entry; nodes fill them and the supervisor
    reads them to decide routing.
    """

    # ── Inputs (set before invocation) ────────────────────────────────
    project_id: str
    section_key: str
    run_id: str
    provider_config_id: str | None
    reasoning_effort: str | None
    input_review_feedback: str | None  # feedback from prior review round (redraft input)

    # ── RFP parser output ─────────────────────────────────────────────
    requirements: list[Requirement]
    requirements_parsed: bool

    # ── Knowledge retriever output ─────────────────────────────────────
    evidence_chunks: list[EvidenceChunk]
    evidence_retrieved: bool

    # ── Section drafter output ─────────────────────────────────────────
    draft_markdown: str
    draft_model_used: str
    draft_created: bool

    # ── Quality reviewer output ────────────────────────────────────────
    review_result: ReviewResult
    review_passed: bool

    # ── Persist output ─────────────────────────────────────────────────
    section_version_id: str | None
    persisted: bool

    # ── Human-in-the-loop ─────────────────────────────────────────────
    human_decision: str | None      # "approved" | "rejected_with_feedback"
    human_feedback: str | None      # feedback from human reviewer on rejection

    # ── Bookkeeping ───────────────────────────────────────────────────
    iteration: int
    max_iterations: int
    error: str | None

    # ── Agent history (累加，使用 operator.add) ──────────────────────
    agent_history: Annotated[list[AgentCall], operator.add]

    # ── Context summary (避免状态过大) ──────────────────────────────
    context_summary: str | None
