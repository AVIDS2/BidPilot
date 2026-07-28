"""Deterministic, provenance-preserving requirement extraction.

Document ingestion may create durable requirement-ledger rows.  That path must
remain replayable and attributable to an immutable source-document version, so
it deliberately does not make an unmetered provider request.  Model-assisted
requirement analysis is performed later by the governed LangGraph node.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.adapters.provider_env import chat_api_key, chat_api_url, chat_model

_DEFAULT_URL = "https://api.openai.com/v1/chat/completions"
_DEFAULT_MODEL = "gpt-4o-mini"
_DEFAULT_KEYWORDS = (
    "shall",
    "must",
    "should",
    "required",
    "mandatory",
    "necessary",
    "必须",
    "应当",
    "应",
    "须",
    "不得",
    "至少",
    "不少于",
    "支持",
    "提供",
    "具备",
    "要求",
)
_HIGH_PRIORITY_KEYWORDS = (
    "shall",
    "must",
    "required",
    "mandatory",
    "必须",
    "应当",
    "须",
    "不得",
    "至少",
    "不少于",
)
_NORMAL_PRIORITY_KEYWORDS = (
    "should",
    "necessary",
    "应",
    "支持",
    "提供",
    "具备",
    "要求",
)


@dataclass(frozen=True)
class RequirementSource:
    """One bounded source fragment plus its immutable-document provenance."""

    source_document_id: str | None
    source_checksum: str | None
    document_version: int | None
    chunk_id: str | None
    chunk_key: str | None
    source_locator_json: dict[str, Any] | None
    content: str


@dataclass(frozen=True)
class ExtractedRequirement:
    section_key: str
    requirement_text: str
    priority: str = "normal"
    source_document_id: str | None = None
    source_checksum: str | None = None
    document_version: int | None = None
    chunk_id: str | None = None
    chunk_key: str | None = None
    source_locator_json: dict[str, Any] | None = None
    extraction_confidence: float = 0.62


# Keep these compatibility helpers while provider configuration moves behind the
# governed workflow. Existing deployment diagnostics still exercise them.
def _api_key() -> str | None:
    return chat_api_key()


def _api_url() -> str:
    return chat_api_url(_DEFAULT_URL)


def _api_model() -> str:
    return chat_model(_DEFAULT_MODEL)


def _as_source(value: RequirementSource | str) -> RequirementSource:
    if isinstance(value, RequirementSource):
        return value
    return RequirementSource(
        source_document_id=None,
        source_checksum=None,
        document_version=None,
        chunk_id=None,
        chunk_key=None,
        source_locator_json=None,
        content=value,
    )


def _normalized_text(value: str) -> str:
    return " ".join(value.split()).casefold()


def _strip_list_marker(value: str) -> str:
    return re.sub(r"^\s*(?:[-*•]+|\d+[.)、])\s*", "", value).strip()


def _contains_keyword(value: str, keywords: tuple[str, ...]) -> bool:
    folded = value.casefold()
    for keyword in keywords:
        if keyword.isascii() and keyword.isalpha():
            if re.search(rf"\b{re.escape(keyword)}\b", value, re.IGNORECASE):
                return True
        elif keyword.casefold() in folded:
            return True
    return False


def _section_key(source: RequirementSource) -> str:
    locator = source.source_locator_json or {}
    nested = locator.get("locator")
    heading = locator.get("heading")
    if not heading and isinstance(nested, dict):
        heading = nested.get("heading")
    if not isinstance(heading, str) or not heading.strip():
        return "extracted"
    normalized = re.sub(r"[^a-z0-9]+", "-", heading.casefold()).strip("-")
    return normalized[:100] or "extracted"


def _priority_for(value: str) -> str:
    if _contains_keyword(value, _HIGH_PRIORITY_KEYWORDS):
        return "high"
    if _contains_keyword(value, _NORMAL_PRIORITY_KEYWORDS):
        return "normal"
    return "low"


def extract_requirements(
    sources: list[RequirementSource | str],
    project_id: str,
    scenario_keywords: list[str] | None = None,
) -> list[ExtractedRequirement]:
    """Extract bounded, source-aware candidate requirements without an LLM call.

    ``project_id`` is retained for the stable adapter contract.  Durable
    provenance belongs to the source document and chunk, not the project text.
    """
    del project_id
    keywords = tuple(
        dict.fromkeys(
            [
                *_DEFAULT_KEYWORDS,
                *(keyword for keyword in (scenario_keywords or []) if keyword.strip()),
            ]
        )
    )
    requirements: list[ExtractedRequirement] = []
    seen: set[tuple[str, str]] = set()

    for raw_source in sources:
        source = _as_source(raw_source)
        for raw_line in source.content.splitlines():
            line = _strip_list_marker(raw_line)
            if len(line) < 6 or not _contains_keyword(line, keywords):
                continue
            identity = (source.source_document_id or source.chunk_key or "untracked", _normalized_text(line))
            if identity in seen:
                continue
            seen.add(identity)
            requirements.append(
                ExtractedRequirement(
                    section_key=_section_key(source),
                    requirement_text=line[:500],
                    priority=_priority_for(line),
                    source_document_id=source.source_document_id,
                    source_checksum=source.source_checksum,
                    document_version=source.document_version,
                    chunk_id=source.chunk_id,
                    chunk_key=source.chunk_key,
                    source_locator_json=source.source_locator_json,
                )
            )
            if len(requirements) >= 50:
                return requirements
    return requirements
