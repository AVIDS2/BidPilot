"""Quality reviewer node: LLM-based review of draft against requirements.

Calls an LLM to evaluate the draft for completeness, compliance, and
evidence usage.  Returns a structured ``ReviewResult`` with a pass/fail
decision, concrete issues, and improvement suggestions.
"""

from __future__ import annotations

import json
import logging
import re
import time

import httpx

from app.adapters.llm import _api_key, _api_model, _api_url
from app.db import SessionLocal
from app.models import Project, ProviderConfig
from app.provider_registry import get_provider_by_id
from sqlalchemy import select

from ..state import BidPilotState, ReviewResult
from ._history import record_agent_call

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a quality reviewer for proposal documents. "
    "Evaluate the draft section against the given requirements. "
    "Return ONLY a JSON object with these exact keys:\n"
    "- passed: boolean (true if quality is acceptable)\n"
    "- issues: array of strings (specific problems found)\n"
    "- suggestions: array of strings (improvement recommendations)\n"
    "- overall_score: number 0.0-1.0 (quality score)\n\n"
    "Be strict but fair. A draft should pass only if it:\n"
    "1. Addresses all high-priority requirements\n"
    "2. Cites evidence where available\n"
    "3. Has no glaring factual gaps\n"
    "4. Is well-structured and professional"
)


def _build_review_prompt(
    section_key: str,
    draft_markdown: str,
    requirements: list[dict],
    evidence_count: int,
) -> str:
    """Build the user prompt for the quality review LLM call."""
    req_lines: list[str] = []
    for r in requirements:
        marker = "[HIGH]" if r.get("priority") == "high" else "[NORMAL]"
        req_lines.append(f"  {marker} {r.get('requirement_text', '')}")
    req_block = "\n".join(req_lines) if req_lines else "  (none)"

    return (
        f"## Section: {section_key}\n\n"
        f"## Requirements\n{req_block}\n\n"
        f"## Evidence Available\n{evidence_count} chunks retrieved\n\n"
        f"## Draft to Review\n{draft_markdown[:6000]}\n\n"
        "Evaluate this draft and return the JSON review object."
    )


def _call_review_llm(
    prompt: str,
    provider_config_id: str | None,
) -> ReviewResult | None:
    """Call the LLM to perform quality review. Returns None on failure."""
    # Resolve provider
    api_key = _api_key()
    url = _api_url()
    model = _api_model()

    if provider_config_id:
        provider = get_provider_by_id(provider_config_id)
        if provider:
            api_key = provider.api_key or api_key
            url = provider.api_url or url
            model = provider.model or model

    if not api_key:
        logger.debug("No LLM API key for quality review — skipping")
        return None

    try:
        resp = httpx.post(
            url,
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.2,
                "max_tokens": 1500,
            },
            timeout=60.0,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]

        # Extract JSON from response (may be wrapped in markdown fences)
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if not match:
            logger.warning("Review LLM response did not contain a JSON object")
            return None

        data = json.loads(match.group())
        return ReviewResult(
            passed=bool(data.get("passed", False)),
            issues=[str(i) for i in data.get("issues", [])],
            suggestions=[str(s) for s in data.get("suggestions", [])],
            overall_score=float(data.get("overall_score", 0.0)),
        )
    except Exception as exc:
        logger.warning("Quality review LLM call failed: %s", exc)
        return None


def _deterministic_review(state: BidPilotState) -> ReviewResult:
    """Fallback review when no LLM is available.

    Performs simple heuristic checks: draft non-empty, minimum length,
    evidence present, iteration count.
    """
    draft = state.get("draft_markdown", "")
    evidence = state.get("evidence_chunks", [])
    requirements = state.get("requirements", [])
    high_reqs = [r for r in requirements if r.get("priority") == "high"]

    issues: list[str] = []
    suggestions: list[str] = []

    if not draft.strip():
        issues.append("Draft is empty")

    if len(draft.strip()) < 200:
        issues.append("Draft is too short (< 200 characters)")

    if not evidence:
        issues.append("No evidence chunks were retrieved")

    if high_reqs and len(draft.strip()) > 0:
        suggestions.append("Verify all high-priority requirements are addressed")

    passed = len(issues) == 0
    score = max(0.0, 1.0 - len(issues) * 0.25)

    return ReviewResult(
        passed=passed,
        issues=issues,
        suggestions=suggestions,
        overall_score=score,
    )


def quality_reviewer_node(state: BidPilotState) -> dict:
    """LangGraph node: review draft quality against requirements.

    Uses an LLM to evaluate completeness, compliance, and evidence usage
    when an API key is available.  Falls back to deterministic heuristic
    checks otherwise.

    Returns:
        Partial state update with ``review_result`` dict,
        ``review_passed`` boolean, and ``agent_history`` record.
    """
    start = time.monotonic()
    section_key: str = state["section_key"]
    draft_markdown: str = state.get("draft_markdown", "")
    requirements = state.get("requirements", [])
    evidence_chunks = state.get("evidence_chunks", [])
    provider_config_id: str | None = state.get("provider_config_id")
    iteration: int = state.get("iteration", 0)

    prompt = _build_review_prompt(
        section_key=section_key,
        draft_markdown=draft_markdown,
        requirements=requirements,
        evidence_count=len(evidence_chunks),
    )

    review = _call_review_llm(prompt, provider_config_id)
    review_method = "llm"
    if review is None:
        review = _deterministic_review(state)
        review_method = "deterministic"

    duration_ms = int((time.monotonic() - start) * 1000)

    logger.info(
        "Quality review for %s: passed=%s score=%.2f issues=%d method=%s",
        section_key,
        review["passed"],
        review["overall_score"],
        len(review["issues"]),
        review_method,
    )

    history = record_agent_call(
        agent="quality_reviewer",
        action="review_draft",
        input_summary=(
            f"section={section_key}, draft_len={len(draft_markdown)}, "
            f"requirements={len(requirements)}, evidence={len(evidence_chunks)}, "
            f"iteration={iteration}, method={review_method}"
        ),
        output_summary=(
            f"passed={review['passed']}, score={review['overall_score']:.2f}, "
            f"issues[{len(review['issues'])}], suggestions[{len(review['suggestions'])}]"
        ),
        duration_ms=duration_ms,
        success=True,
    )

    return {
        "review_result": review,
        "review_passed": review["passed"],
        "agent_history": history,
    }
