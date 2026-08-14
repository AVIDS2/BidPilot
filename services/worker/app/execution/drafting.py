"""Drafting execution logic: retrieve validated evidence, call LLM, and persist a section."""

import logging
from datetime import UTC, datetime
from typing import Sequence

from app.adapters.llm import draft_section as draft_section_openai
from app.adapters.anthropic_llm import draft_section as draft_section_anthropic
from app.adapters.provider_errors import ProviderInvocationError
from app.db import SessionLocal
from app.execution.embedding_capacity import generate_metered_embedding
from app.provider_registry import get_provider_by_id
from app.execution.model_usage import record_workflow_model_usage
from app.retrieval.reranker import rerank_candidates
from app.models import (
    Deliverable,
    DeliverableSection,
    Evidence,
    ExecutionRun,
    Project,
    RuntimeRun,
    SectionVersion,
    User,
)
from sqlalchemy import select

from app.retrieval.section_query import expand_section_retrieval_query, section_fallback_query
from contracts import EmbeddingOutcome, EmbeddingOutcomeStatus, RetrievalCandidate
from contracts.retrieval_service import retrieve_project_evidence

logger = logging.getLogger(__name__)


def _retrieve_evidence(
    project_id: str,
    section_key: str,
    top_k: int = 5,
    *,
    run_id: str | None = None,
) -> tuple[RetrievalCandidate, ...]:
    """Retrieve profile-safe, citation-validated evidence for a draft section."""
    query = expand_section_retrieval_query(section_key)
    db = SessionLocal()
    try:
        project = db.get(Project, project_id)
        runtime_run = (
            db.scalar(
                select(RuntimeRun)
                .where(RuntimeRun.execution_run_id == run_id)
                .order_by(RuntimeRun.created_at.desc())
                .limit(1)
            )
            if run_id
            else None
        )
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
                workload="embedding_legacy_workflow_evidence_query",
                text=query,
                execution_run_id=run_id,
                runtime_run_id=runtime_run.id,
            )
        result = retrieve_project_evidence(
            db,
            project_id=project_id,
            raw_query=query,
            profile_id=query_embedding.profile_id if query_embedding.is_success else None,
            query_embedding=query_embedding.embedding if query_embedding.is_success else None,
            top_k=top_k,
            reranker=rerank_candidates,
        )
        if not result.candidates:
            fallback = section_fallback_query(section_key)
            if fallback and fallback != query:
                result = retrieve_project_evidence(
                    db,
                    project_id=project_id,
                    raw_query=fallback,
                    profile_id=None,
                    query_embedding=None,
                    top_k=top_k,
                    reranker=rerank_candidates,
                )
        return result.candidates
    finally:
        db.close()


def _link_evidence(
    db,
    project_id: str,
    section_version_id: str,
    candidates: Sequence[RetrievalCandidate],
) -> None:
    """Create evidence records from validated retrieval candidates."""
    for candidate in candidates:
        ev = Evidence(
            project_id=project_id,
            section_version_id=section_version_id,
            source_document_id=candidate.source_document_id,
            chunk_id=candidate.chunk_id,
            quote_text=candidate.content[:500],
            locator_json=candidate.locator.model_dump(exclude_none=True),
            confidence=None,
        )
        db.add(ev)


def run_draft(
    run_id: str,
    project_id: str,
    section_key: str,
    review_feedback: str | None = None,
    provider_config_id: str | None = None,
    reasoning_effort: str | None = None,
    deliverable_section_id: str | None = None,
) -> dict[str, str]:
    """Execute the full drafting pipeline for a section.

    Args:
        provider_config_id: Optional user provider config ID. When provided,
                            resolves the provider from the DB and uses its
                            credentials instead of env-var defaults.
    """
    db = SessionLocal()
    try:
        run = db.get(ExecutionRun, run_id)
        if run is None:
            return {"run_id": run_id, "status": "not_found"}
        run.status = "running"
        run.started_at = datetime.now(UTC)
        db.commit()
    finally:
        db.close()

    # Retrieve evidence
    evidence_candidates = _retrieve_evidence(project_id, section_key, run_id=run_id)
    evidence_texts = [candidate.content for candidate in evidence_candidates]

    # Look up scenario-specific system prompt
    system_prompt = None
    try:
        db2 = SessionLocal()
        project = db2.get(Project, project_id)
        if project and project.scenario_package:
            from app.scenarios.templates import get_drafting_prompt
            system_prompt = get_drafting_prompt(project.scenario_package)
        db2.close()
    except Exception:
        pass  # Fallback to default prompt

    # Call LLM adapter with optional user-provided provider config
    provider_params = None
    if provider_config_id:
        provider_params = get_provider_by_id(provider_config_id)
        if provider_params is None:
            raise ProviderInvocationError(
                "provider_config_missing",
                "所选模型提供商配置已不可用，请重新选择后再试。",
                retryable=False,
            )

    provider_config_dict = None
    if provider_params:
        provider_config_dict = {
            "api_key": provider_params.api_key,
            "api_url": provider_params.api_url,
            "model": provider_params.model,
        }

    if provider_params and provider_params.provider_type == "anthropic":
        result = draft_section_anthropic(
            section_key, evidence_texts, project_id,
            review_feedback=review_feedback,
            system_prompt=system_prompt,
            provider_config=provider_config_dict,
            reasoning_effort=reasoning_effort,
        )
    else:
        # Default to OpenAI-compatible (also handles fallback when no provider_config)
        result = draft_section_openai(
            section_key, evidence_texts, project_id,
            review_feedback=review_feedback,
            system_prompt=system_prompt,
            provider_config=provider_config_dict,
            reasoning_effort=reasoning_effort,
        )

    record_workflow_model_usage(
        run_id=run_id,
        provider_type=provider_params.provider_type if provider_params else "openai",
        model_name=result.model_used,
        measurement=result.usage,
    )

    # Write section version if a matching section exists
    section_version_id = None
    db = SessionLocal()
    try:
        if deliverable_section_id:
            section = db.get(DeliverableSection, deliverable_section_id)
            deliverable = db.get(Deliverable, section.deliverable_id) if section else None
            if section is None or deliverable is None or deliverable.project_id != project_id:
                raise ValueError("deliverable_section_not_found")
            if section.section_key != section_key:
                raise ValueError("deliverable_section_key_mismatch")
        else:
            matching_sections = list(db.scalars(
                select(DeliverableSection)
                .join(Deliverable, Deliverable.id == DeliverableSection.deliverable_id)
                .where(
                    Deliverable.project_id == project_id,
                    DeliverableSection.section_key == section_key,
                )
                .limit(2)
            ).all())
            if len(matching_sections) > 1:
                raise ValueError("deliverable_section_ambiguous")
            section = matching_sections[0] if matching_sections else None
        if section is not None:
            # Determine next version number
            existing = db.scalar(
                select(SectionVersion)
                .where(SectionVersion.deliverable_section_id == section.id)
                .order_by(SectionVersion.version_number.desc())
                .limit(1)
            )
            next_version = (existing.version_number + 1) if existing else 1
            sv = SectionVersion(
                deliverable_section_id=section.id,
                version_number=next_version,
                content_markdown=result.content_markdown,
                created_by_actor="ai",
                generation_run_id=run_id,
            )
            db.add(sv)
            db.flush()
            section_version_id = sv.id

            # Link evidence to this section version
            if evidence_candidates:
                _link_evidence(db, project_id, section_version_id, evidence_candidates)

            # If no evidence found, add a missing-evidence marker
            if not evidence_candidates:
                ev = Evidence(
                    project_id=project_id,
                    section_version_id=section_version_id,
                    quote_text="[NO EVIDENCE FOUND] No relevant knowledge chunks were retrieved for this section.",
                    locator_json={"marker": "missing-evidence"},
                    confidence=0.0,
                )
                db.add(ev)

            db.commit()
    finally:
        db.close()

    # Update run status
    db = SessionLocal()
    try:
        run = db.get(ExecutionRun, run_id)
        if run is not None:
            run.status = "succeeded"
            run.finished_at = datetime.now(UTC)
            run.output_json = {
                "section_key": section_key,
                "model_used": result.model_used,
                "evidence_count": len(evidence_candidates),
                "section_version_id": section_version_id,
            }
            db.commit()
    finally:
        db.close()

    return {"run_id": run_id, "status": "succeeded", "model_used": result.model_used}
