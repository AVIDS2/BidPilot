"""RFP parser node: extract structured requirements from parsed document assets.

Queries ParsedAsset.content_json for all source documents in the project,
concatenates their text, then uses an LLM (or pattern-based fallback) to
extract structured requirements.  Persists them as RequirementItem rows so
downstream nodes can reference them.
"""

from __future__ import annotations

import json
import logging
import re
import time

from app.adapters.llm import _api_key as _llm_api_key
from app.adapters.llm import _api_model as _llm_api_model
from app.adapters.llm import _api_url as _llm_api_url
from app.db import SessionLocal
from app.models import (
    Bundle,
    KnowledgeChunk,
    ParsedAsset,
    Project,
    RequirementItem,
    SourceDocument,
)
from app.scenarios.registry import get_scenario_or_raise
from sqlalchemy import select

from ..state import BidPilotState, Requirement
from ._history import record_agent_call

logger = logging.getLogger(__name__)

# ── LLM extraction ────────────────────────────────────────────────────

_SYSTEM_PROMPT = (
    "You are a requirements analyst. Extract structured requirements from "
    "documents. Return only a valid JSON array of objects with keys: "
    "section_key (kebab-case), requirement_text, priority (high/normal/low)."
)


def _build_user_prompt(text: str, keywords: list[str]) -> str:
    kw_list = ", ".join(keywords)
    return (
        "Analyze the following document text and extract structured requirements.\n"
        "For each requirement:\n"
        "- section_key: a short kebab-case identifier for the section it belongs to\n"
        "- requirement_text: the full requirement text\n"
        '- priority: "high" for mandatory/shall/must, "normal" for should/recommended, '
        '"low" for optional/may\n\n'
        f"Focus especially on keywords: {kw_list}\n\n"
        "Return as a JSON array.\n\n"
        f"Document text:\n{text[:12000]}"
    )


def _extract_via_llm(text: str, keywords: list[str]) -> list[Requirement] | None:
    """Call OpenAI-compatible chat API to extract requirements.  Returns None on failure."""
    import httpx

    api_key = _llm_api_key()
    if not api_key:
        return None

    url = _llm_api_url()
    model = _llm_api_model()

    try:
        resp = httpx.post(
            url,
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": _build_user_prompt(text, keywords)},
                ],
                "temperature": 0.1,
                "max_tokens": 3000,
            },
            timeout=60.0,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]

        # Extract JSON array from response (may be wrapped in markdown fences)
        match = re.search(r"\[.*\]", content, re.DOTALL)
        if not match:
            logger.warning("LLM response did not contain a JSON array")
            return None

        items = json.loads(match.group())
        return [
            Requirement(
                section_key=item.get("section_key", "extracted"),
                requirement_text=item.get("requirement_text", ""),
                priority=item.get("priority", "normal"),
            )
            for item in items
            if item.get("requirement_text")
        ]
    except Exception as exc:
        logger.warning("LLM requirement extraction failed: %s", exc)
        return None


# ── Pattern-based fallback ─────────────────────────────────────────────

_KEYWORDS_DEFAULT = ["shall", "must", "should", "required", "mandatory", "necessary"]


def _extract_via_pattern(text: str, keywords: list[str] | None) -> list[Requirement]:
    """Simple regex-based requirement extraction."""
    kw = keywords or _KEYWORDS_DEFAULT
    pattern = re.compile(r"\b(" + "|".join(kw) + r")\b", re.IGNORECASE)
    requirements: list[Requirement] = []

    for line in text.split("\n"):
        line = line.strip().lstrip("- •*0-9). ")
        if not line or len(line) < 10:
            continue
        if pattern.search(line):
            priority = (
                "high"
                if re.search(r"\b(must|shall|mandatory|required)\b", line, re.IGNORECASE)
                else "normal"
            )
            requirements.append(
                Requirement(
                    section_key="extracted",
                    requirement_text=line[:500],
                    priority=priority,
                )
            )
    return requirements[:50]


# ── Node entry point ───────────────────────────────────────────────────


def rfp_parser_node(state: BidPilotState) -> dict:
    """LangGraph node: extract requirements from project source documents.

    Reads ParsedAsset.content_json for all documents in the project's bundles,
    concatenates their text, then calls the LLM (or pattern fallback) to
    produce a structured requirement list.  Persists requirements as
    RequirementItem rows.

    Returns:
        Partial state update with ``requirements`` list,
        ``requirements_parsed`` flag, and ``agent_history`` record.
    """
    start = time.monotonic()
    project_id: str = state["project_id"]
    section_key: str = state["section_key"]

    db = SessionLocal()
    try:
        # Determine scenario keywords
        project = db.get(Project, project_id)
        keywords = _KEYWORDS_DEFAULT
        if project and project.scenario_package:
            try:
                pkg = get_scenario_or_raise(project.scenario_package)
                keywords = pkg.requirement_keywords
            except ValueError:
                pass

        # Gather all parsed asset text for this project
        stmt = (
            select(ParsedAsset)
            .join(SourceDocument, ParsedAsset.source_document_id == SourceDocument.id)
            .join(Bundle, SourceDocument.bundle_id == Bundle.id)
            .where(Bundle.project_id == project_id)
        )
        assets = list(db.scalars(stmt).all())

        texts: list[str] = []
        for asset in assets:
            cj = asset.content_json
            if not cj:
                continue
            # content_json may be {"text": "..."} or a raw string
            if isinstance(cj, dict):
                texts.append(cj.get("text", json.dumps(cj)))
            elif isinstance(cj, str):
                texts.append(cj)

        combined_text = "\n\n".join(texts)

        if not combined_text.strip():
            logger.info("No parsed asset text found for project %s", project_id)
            duration_ms = int((time.monotonic() - start) * 1000)
            history = record_agent_call(
                agent="rfp_parser",
                action="extract_requirements",
                input_summary=f"project_id={project_id}, section={section_key}, no_text",
                output_summary="requirements[0], empty (no parsed assets)",
                duration_ms=duration_ms,
                success=True,
            )
            return {
                "requirements": [],
                "requirements_parsed": True,
                "agent_history": history,
            }

        # Try LLM extraction first, fall back to pattern-based
        requirements = _extract_via_llm(combined_text, keywords)
        extraction_method = "llm"
        if requirements is None:
            requirements = _extract_via_pattern(combined_text, keywords)
            extraction_method = "pattern"

        # Persist as RequirementItem rows
        for req in requirements:
            item = RequirementItem(
                project_id=project_id,
                section_key=req["section_key"],
                requirement_text=req["requirement_text"],
                priority=req["priority"],
                status="open",
            )
            db.add(item)
        db.commit()

        duration_ms = int((time.monotonic() - start) * 1000)
        logger.info(
            "Extracted %d requirements for project %s (method=%s)",
            len(requirements),
            project_id,
            extraction_method,
        )

        history = record_agent_call(
            agent="rfp_parser",
            action="extract_requirements",
            input_summary=f"project_id={project_id}, section={section_key}, text_len={len(combined_text)}, method={extraction_method}",
            output_summary=f"requirements[{len(requirements)}], high={sum(1 for r in requirements if r['priority'] == 'high')}",
            duration_ms=duration_ms,
            success=True,
        )

        return {
            "requirements": requirements,
            "requirements_parsed": True,
            "agent_history": history,
        }
    except Exception as exc:
        duration_ms = int((time.monotonic() - start) * 1000)
        logger.exception("rfp_parser_node failed for project %s", project_id)
        db.rollback()

        history = record_agent_call(
            agent="rfp_parser",
            action="extract_requirements",
            input_summary=f"project_id={project_id}, section={section_key}",
            output_summary=f"ERROR: {exc}",
            duration_ms=duration_ms,
            success=False,
            error=str(exc),
        )

        return {
            "requirements": [],
            "requirements_parsed": True,
            "error": f"rfp_parser: {exc}",
            "agent_history": history,
        }
    finally:
        db.close()
