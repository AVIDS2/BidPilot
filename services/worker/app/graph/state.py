"""BidPilot LangGraph state definition.

Central TypedDict shared by every node in the drafting graph.
Each node receives the full state and returns a partial update.
"""

from __future__ import annotations

import operator
from typing import Annotated, NotRequired, TypedDict



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
    """A single retrieved chunk with ranking signals and validated locator metadata."""

    chunk_id: str
    source_document_id: str
    content: str
    retrieval_score: float
    retrieval_methods: list[str]
    locator_json: dict
    chunk_index: int
    evidence_set_item_id: NotRequired[str]
    source_document_version: NotRequired[int]


class MemoryContextEntry(TypedDict):
    """A compact, provenance-preserving memory excerpt safe for one workflow."""

    title: str
    body_markdown: str
    scope: str
    kind: str
    citations: list[str]


class Requirement(TypedDict):
    """A requirement before or after it receives a durable ledger identifier."""

    id: NotRequired[str]
    section_key: str
    requirement_text: str
    priority: str  # "high" | "normal" | "low"


class ReviewResult(TypedDict):
    """Structured output from the quality reviewer."""

    passed: bool
    issues: list[str]
    suggestions: list[str]
    overall_score: float


class ClaimCandidate(TypedDict):
    """A server-validated draft assertion awaiting human verification."""

    claim_text: str
    claim_type: str
    requirement_ids: list[str]
    evidence_chunk_ids: list[str]


class ContentPlanItem(TypedDict):
    """One planned writing element (evidence pick, table, or figure)."""

    kind: str
    title: str
    detail: str
    source_ref: str | None


class ContentPlan(TypedDict):
    """Deterministic writing plan produced before section drafting."""

    section_key: str
    summary: str
    outline: list[str]
    key_points: list[str]
    evidence_picks: list[ContentPlanItem]
    tables: list[ContentPlanItem]
    figures: list[ContentPlanItem]
    gaps: list[str]


class BidPilotState(TypedDict):
    """Shared state for the BidPilot LangGraph agent.

    Fields are populated progressively as the graph traverses nodes.
    All fields are optional at entry; nodes fill them and the supervisor
    reads them to decide routing.
    """

    # ── Inputs (set before invocation) ────────────────────────────────
    project_id: str
    section_key: str
    deliverable_section_id: str | None
    run_id: str
    runtime_run_id: str | None
    provider_config_id: str | None
    reasoning_effort: str | None
    input_review_feedback: str | None  # feedback from prior review round (redraft input)

    # ── RFP parser output ─────────────────────────────────────────────
    requirements: list[Requirement]
    requirements_parsed: bool

    # ── Knowledge retriever output ─────────────────────────────────────
    evidence_set_id: str | None
    evidence_set_status: str | None
    evidence_set_unmet_requirement_ids: list[str]
    evidence_set_degraded_reasons: list[str]
    evidence_chunks: list[EvidenceChunk]
    evidence_retrieved: bool
    retrieval_candidate_count: int | None
    retrieval_fused_candidate_count: int | None
    retrieval_reranked_candidate_count: int | None
    retrieval_latency_ms: int | None

    # ── Content plan (pre-draft structure) ────────────────────────────
    content_plan: ContentPlan | None
    content_plan_ready: bool
    response_plan_id: str | None
    response_plan_section_id: str | None
    response_plan_evidence_binding_id: str | None
    response_plan_version: int | None

    # ── Governed memory context ───────────────────────────────────────
    memory_context_loaded: bool
    memory_context_items: list[MemoryContextEntry]
    memory_context_version: str | None
    memory_context_degraded_reasons: list[str]
    memory_proposal_ids: list[str]

    # ── Section drafter output ─────────────────────────────────────────
    draft_markdown: str
    draft_model_used: str
    draft_created: bool
    provider_error_code: str | None

    # ── Quality reviewer output ────────────────────────────────────────
    review_result: ReviewResult
    review_passed: bool
    # "passed" | "failed" | "degraded" | "blocked" | "not_started".
    # A degraded automatic review is deliberately not an automatic pass.
    review_status: str
    review_degradation_code: str | None
    claim_candidates: list[ClaimCandidate]
    claim_integrity_status: str

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
