"""Knowledge retriever node backed by the shared Retrieval 2 pipeline."""

from __future__ import annotations

import logging
import time

from app.db import SessionLocal
from app.execution.embedding_capacity import generate_metered_embedding
from app.models import Project, RuntimeRun, User
from app.retrieval.reranker import rerank_candidates
from contracts import EmbeddingOutcome, EmbeddingOutcomeStatus
from contracts.retrieval_service import retrieve_project_evidence

from ..state import BidPilotState, EvidenceChunk
from ._history import record_agent_call

logger = logging.getLogger(__name__)

_TOP_K = 5


def knowledge_retriever_node(state: BidPilotState) -> dict:
    """Retrieve validated project evidence without raw SQL or broad fallback."""
    started = time.monotonic()
    project_id: str = state["project_id"]
    section_key: str = state["section_key"]
    query = section_key.replace("-", " ")

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
        chunks: list[EvidenceChunk] = [
            EvidenceChunk(
                chunk_id=candidate.chunk_id,
                source_document_id=candidate.source_document_id,
                content=candidate.content[:500],
                retrieval_score=candidate.final_score,
                retrieval_methods=list(candidate.methods),
                locator_json=candidate.locator.model_dump(exclude_none=True),
                chunk_index=candidate.locator.chunk_index,
            )
            for candidate in result.candidates
        ]
        duration_ms = int((time.monotonic() - started) * 1000)
        methods = sorted({method for chunk in chunks for method in chunk["retrieval_methods"]})
        history = record_agent_call(
            agent="knowledge_retriever",
            action="retrieve_evidence",
            input_summary=f"project_id={project_id}, section={section_key}",
            output_summary=(
                f"evidence_chunks[{len(chunks)}], methods={','.join(methods) or 'none'}, "
                f"degraded={','.join(result.degraded_reasons) or 'none'}, "
                f"embedding={query_embedding.error_code or 'available'}"
            ),
            duration_ms=duration_ms,
            success=True,
        )
        return {
            "evidence_chunks": chunks,
            "evidence_retrieved": True,
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
