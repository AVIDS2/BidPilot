"""Knowledge retriever node backed by the shared Retrieval 2 pipeline."""

from __future__ import annotations

import logging
import time

from app.db import SessionLocal
from app.execution.embedding_capacity import generate_metered_embedding
from app.models import Project, RuntimeRun, User
from app.retrieval.evidence_sets import capture_evidence_set
from app.retrieval.reranker import rerank_candidates
from app.retrieval.section_query import expand_section_retrieval_query, section_fallback_query
from contracts import EmbeddingOutcome, EmbeddingOutcomeStatus
from contracts.retrieval_service import retrieve_project_evidence

from ..state import BidPilotState
from ._history import record_agent_call

logger = logging.getLogger(__name__)

_TOP_K = 5
def knowledge_retriever_node(state: BidPilotState) -> dict:
    """Retrieve validated project evidence without raw SQL or broad fallback."""
    started = time.monotonic()
    project_id: str = state["project_id"]
    section_key: str = state["section_key"]
    # Expand English section keys into bilingual lexical queries so Chinese
    # FTS / trigram corpora can match (e.g. technical-approach → 技术方案).
    query = expand_section_retrieval_query(section_key)
    query_used = query
    used_fallback = False

    db = SessionLocal()
    try:
        runtime_run_id = state.get("runtime_run_id")
        project = db.get(Project, project_id)
        runtime_run = db.get(RuntimeRun, runtime_run_id) if runtime_run_id else None
        user = db.get(User, runtime_run.user_id) if runtime_run is not None else None
        if (
            project is None
            or runtime_run is None
            or runtime_run.project_id != project.id
            or runtime_run.org_id != project.org_id
            or user is None
            or user.org_id != project.org_id
            or user.disabled
        ):
            # A workflow may still use lexical project search, but it must not
            # disclose a query to an embedding provider without a trusted actor.
            query_embedding = EmbeddingOutcome(
                status=EmbeddingOutcomeStatus.NOT_CONFIGURED,
                error_code="invalid_runtime_principal",
            )
        else:
            query_embedding = generate_metered_embedding(
                db,
                org_id=project.org_id,
                user_id=user.id,
                project_id=project.id,
                workload="embedding_workflow_evidence_query",
                text=query,
                execution_run_id=state.get("run_id"),
                runtime_run_id=runtime_run.id,
            )
        result = retrieve_project_evidence(
            db,
            project_id=project_id,
            raw_query=query,
            profile_id=query_embedding.profile_id if query_embedding.is_success else None,
            query_embedding=query_embedding.embedding if query_embedding.is_success else None,
            top_k=_TOP_K,
            reranker=rerank_candidates,
        )
        # Empty primary hit: retry with a pure Chinese domain fallback. Dense
        # embedding is intentionally not re-metered for the fallback pass.
        if not result.candidates:
            fallback = section_fallback_query(section_key)
            if fallback and fallback != query:
                used_fallback = True
                query_used = fallback
                result = retrieve_project_evidence(
                    db,
                    project_id=project_id,
                    raw_query=fallback,
                    profile_id=None,
                    query_embedding=None,
                    top_k=_TOP_K,
                    reranker=rerank_candidates,
                )
        degraded = list(result.degraded_reasons)
        if used_fallback:
            degraded.append("section_query_fallback")
        evidence_set = capture_evidence_set(
            db,
            project_id=project_id,
            execution_run_id=state["run_id"],
            section_key=section_key,
            query_text=query_used,
            retrieval_profile_id=result.profile_id,
            degraded_reasons=degraded,
            candidates=result.candidates,
        )
        # The evidence set is the durable boundary before a provider sees any
        # retrieved material. Commit it before returning state to LangGraph.
        db.commit()
        chunks = evidence_set.evidence_chunks
        duration_ms = int((time.monotonic() - started) * 1000)
        methods = sorted({method for chunk in chunks for method in chunk["retrieval_methods"]})
        all_degraded = list(dict.fromkeys([*degraded, *evidence_set.degraded_reasons]))
        history = record_agent_call(
            agent="knowledge_retriever",
            action="retrieve_evidence",
            input_summary=(
                f"project_id={project_id}, section={section_key}, "
                f"query={query_used[:80]}"
            ),
            output_summary=(
                f"evidence_chunks[{len(chunks)}], methods={','.join(methods) or 'none'}, "
                f"evidence_set={evidence_set.status}, "
                f"degraded={','.join(all_degraded) or 'none'}, "
                f"embedding={query_embedding.error_code or 'available'}, "
                f"fallback={used_fallback}"
            ),
            duration_ms=duration_ms,
            success=True,
        )
        retrieval_trace = result.trace
        return {
            "evidence_set_id": evidence_set.id,
            "evidence_set_status": evidence_set.status,
            "evidence_set_unmet_requirement_ids": list(evidence_set.unmet_requirement_ids),
            "evidence_set_degraded_reasons": list(
                dict.fromkeys([*all_degraded, *evidence_set.rejected_reasons])
            ),
            "evidence_chunks": chunks,
            "evidence_retrieved": True,
            # Numeric trace fields are safe to persist into the runtime event.
            # The expanded query, candidate content, and provider request stay
            # in the retrieval boundary and never become observability output.
            "retrieval_candidate_count": (
                retrieval_trace.returned_candidate_count if retrieval_trace is not None else None
            ),
            "retrieval_fused_candidate_count": (
                retrieval_trace.fused_candidate_count if retrieval_trace is not None else None
            ),
            "retrieval_reranked_candidate_count": (
                retrieval_trace.reranked_candidate_count if retrieval_trace is not None else None
            ),
            "retrieval_latency_ms": retrieval_trace.latency_ms if retrieval_trace is not None else None,
            "agent_history": history,
        }
    except Exception:
        duration_ms = int((time.monotonic() - started) * 1000)
        logger.exception(
            "knowledge_retriever_node failed for project %s, section %s",
            project_id,
            section_key,
        )
        history = record_agent_call(
            agent="knowledge_retriever",
            action="retrieve_evidence",
            input_summary=f"project_id={project_id}, section={section_key}",
            output_summary="retrieval unavailable",
            duration_ms=duration_ms,
            success=False,
            error="retrieval_unavailable",
        )
        return {
            "evidence_chunks": [],
            "evidence_retrieved": True,
            "error": "knowledge_retriever_unavailable",
            "agent_history": history,
        }
    finally:
        db.close()
