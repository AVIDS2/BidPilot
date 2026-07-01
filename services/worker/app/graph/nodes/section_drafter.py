"""Section drafter node: generate draft content via LLM with retry.

Wraps the existing OpenAI / Anthropic adapter calls behind a tenacity
retry decorator (3 attempts, exponential backoff).  Reads
``provider_config_id`` from state to honour user-specific provider
settings.
"""

from __future__ import annotations

import logging
import time

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.adapters.llm import draft_section as draft_section_openai
from app.adapters.llm import DraftResult
from app.adapters.anthropic_llm import draft_section as draft_section_anthropic
from app.db import SessionLocal
from app.models import Project, ProviderConfig
from app.provider_registry import get_provider_by_id
from sqlalchemy import select

from ..state import BidPilotState
from ._history import record_agent_call

logger = logging.getLogger(__name__)

_MAX_ATTEMPTS = 3


class DraftError(Exception):
    """Raised when all LLM draft attempts are exhausted."""


@retry(
    stop=stop_after_attempt(_MAX_ATTEMPTS),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type((Exception,)),
    reraise=True,
    before_sleep=lambda retry_state: logger.warning(
        "Draft attempt %d failed: %s — retrying in %.1fs",
        retry_state.attempt_number,
        retry_state.outcome.exception() if retry_state.outcome else "unknown",
        retry_state.next_action.sleep if retry_state.next_action else 0,
    ),
)
def _draft_with_retry(
    section_key: str,
    evidence_texts: list[str],
    project_id: str,
    review_feedback: str | None,
    system_prompt: str | None,
    provider_config_dict: dict | None,
    provider_type: str,
    reasoning_effort: str | None,
) -> DraftResult:
    """Call the appropriate LLM adapter with tenacity retry.

    Raises on failure after all retries are exhausted so the caller can
    record the error in state.
    """
    if provider_type == "anthropic":
        return draft_section_anthropic(
            section_key,
            evidence_texts,
            project_id,
            review_feedback=review_feedback,
            system_prompt=system_prompt,
            provider_config=provider_config_dict,
            reasoning_effort=reasoning_effort,
        )
    return draft_section_openai(
        section_key,
        evidence_texts,
        project_id,
        review_feedback=review_feedback,
        system_prompt=system_prompt,
        provider_config=provider_config_dict,
        reasoning_effort=reasoning_effort,
    )


def _resolve_provider(provider_config_id: str | None) -> tuple[dict | None, str]:
    """Resolve provider configuration from DB.

    Returns (provider_config_dict, provider_type).
    """
    if not provider_config_id:
        return None, "openai"

    provider_params = get_provider_by_id(provider_config_id)
    if provider_params is None:
        return None, "openai"

    config_dict = {
        "api_key": provider_params.api_key,
        "api_url": provider_params.api_url,
        "model": provider_params.model,
    }
    return config_dict, provider_params.provider_type


def _load_system_prompt(project_id: str) -> str | None:
    """Load scenario-specific system prompt from the project."""
    db = SessionLocal()
    try:
        project = db.get(Project, project_id)
        if project and project.scenario_package:
            try:
                from app.scenarios.templates import get_drafting_prompt

                return get_drafting_prompt(project.scenario_package)
            except Exception:
                pass
        return None
    finally:
        db.close()


def section_drafter_node(state: BidPilotState) -> dict:
    """LangGraph node: draft a section using evidence and LLM.

    Reads evidence chunk contents from state, resolves the provider
    configuration, loads the scenario system prompt, and calls the LLM
    adapter with tenacity retry (3 attempts, exponential backoff).

    On success returns ``draft_markdown``, ``draft_model_used``,
    ``draft_created`` = True, and ``agent_history`` record.
    On failure after all retries returns an error string,
    ``draft_created`` = False, and ``agent_history`` record.

    Returns:
        Partial state update with drafting results.
    """
    start = time.monotonic()
    section_key: str = state["section_key"]
    project_id: str = state["project_id"]
    provider_config_id: str | None = state.get("provider_config_id")
    reasoning_effort: str | None = state.get("reasoning_effort")
    # Use human_feedback (from HITL) if available, otherwise input_review_feedback
    review_feedback: str | None = state.get("human_feedback") or state.get("input_review_feedback")
    evidence_chunks = state.get("evidence_chunks", [])
    iteration: int = state.get("iteration", 0)

    evidence_texts = [chunk["content"] for chunk in evidence_chunks]

    provider_config_dict, provider_type = _resolve_provider(provider_config_id)
    system_prompt = _load_system_prompt(project_id)

    try:
        result = _draft_with_retry(
            section_key=section_key,
            evidence_texts=evidence_texts,
            project_id=project_id,
            review_feedback=review_feedback,
            system_prompt=system_prompt,
            provider_config_dict=provider_config_dict,
            provider_type=provider_type,
            reasoning_effort=reasoning_effort,
        )
        duration_ms = int((time.monotonic() - start) * 1000)
        logger.info(
            "Drafted section %s with model %s (evidence=%d, iteration=%d)",
            section_key,
            result.model_used,
            len(evidence_texts),
            iteration,
        )

        history = record_agent_call(
            agent="section_drafter",
            action="draft_section",
            input_summary=(
                f"section={section_key}, evidence={len(evidence_texts)}, "
                f"iteration={iteration}, provider={provider_type}, "
                f"has_feedback={review_feedback is not None}"
            ),
            output_summary=(
                f"model={result.model_used}, draft_len={len(result.content_markdown)}, "
                f"draft_created=True"
            ),
            duration_ms=duration_ms,
            success=True,
        )

        return {
            "draft_markdown": result.content_markdown,
            "draft_model_used": result.model_used,
            "draft_created": True,
            "iteration": iteration + 1,
            "agent_history": history,
        }
    except Exception as exc:
        duration_ms = int((time.monotonic() - start) * 1000)
        logger.exception("section_drafter_node failed for section %s", section_key)

        history = record_agent_call(
            agent="section_drafter",
            action="draft_section",
            input_summary=(
                f"section={section_key}, evidence={len(evidence_texts)}, "
                f"iteration={iteration}, provider={provider_type}"
            ),
            output_summary=f"ERROR: {exc}",
            duration_ms=duration_ms,
            success=False,
            error=str(exc),
        )

        return {
            "draft_markdown": "",
            "draft_model_used": "",
            "draft_created": False,
            "iteration": iteration + 1,
            "error": f"section_drafter: {exc}",
            "agent_history": history,
        }
