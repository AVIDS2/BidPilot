"""Requirement extraction adapter.

Extracts structured requirements from knowledge chunks using LLM.
Falls back to a simple pattern-based extraction when no API key is configured.
"""

import logging
import re
from dataclasses import dataclass, field

import httpx

from app.adapters.provider_env import chat_api_key, chat_api_url, chat_model

logger = logging.getLogger(__name__)

_DEFAULT_URL = "https://api.openai.com/v1/chat/completions"
_DEFAULT_MODEL = "gpt-4o-mini"


@dataclass
class ExtractedRequirement:
    section_key: str
    requirement_text: str
    priority: str = "normal"


def _api_key() -> str | None:
    return chat_api_key()


def _api_url() -> str:
    return chat_api_url(_DEFAULT_URL)


def _api_model() -> str:
    return chat_model(_DEFAULT_MODEL)


def _extract_requirements_stub(chunks_text: list[str], keywords: list[str] | None = None) -> list[ExtractedRequirement]:
    """Pattern-based requirement extraction stub.

    Looks for lines containing scenario-specific keywords (or defaults).
    """
    requirements: list[ExtractedRequirement] = []
    kw = keywords or ["shall", "must", "should", "required", "mandatory", "necessary"]
    pattern = re.compile(r"\b(" + "|".join(kw) + r")\b", re.IGNORECASE)

    for text in chunks_text:
        for line in text.split("\n"):
            line = line.strip().lstrip("- •*0-9). ")
            if not line or len(line) < 10:
                continue
            if pattern.search(line):
                priority = "high" if re.search(r"\b(must|shall|mandatory|required)\b", line, re.IGNORECASE) else "normal"
                requirements.append(ExtractedRequirement(
                    section_key="extracted",
                    requirement_text=line[:500],
                    priority=priority,
                ))
    return requirements[:50]  # Cap at 50


def extract_requirements(chunks_text: list[str], project_id: str, scenario_keywords: list[str] | None = None) -> list[ExtractedRequirement]:
    """Extract structured requirements from text chunks.

    Uses LLM when available, falls back to pattern-based extraction.
    """
    api_key = _api_key()
    if not api_key:
        return _extract_requirements_stub(chunks_text, keywords=scenario_keywords)

    combined = "\n\n".join(chunks_text[:20])  # Limit context size
    prompt = f"""Analyze the following document text and extract structured requirements.
For each requirement, provide:
- section_key: a short kebab-case identifier for the section it belongs to
- requirement_text: the full requirement text
- priority: "high" for mandatory/shall/must, "normal" for should/recommended, "low" for optional/may

Return as a JSON array of objects with keys: section_key, requirement_text, priority.

Document text:
{combined}
"""
    url = _api_url()
    model = _api_model()

    try:
        resp = httpx.post(
            url,
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": "You are a requirements analyst. Extract structured requirements from documents. Return only valid JSON."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.1,
                "max_tokens": 3000,
            },
            timeout=60.0,
        )
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]

        # Parse JSON from response
        import json
        # Try to find JSON array in response
        match = re.search(r"\[.*\]", content, re.DOTALL)
        if match:
            items = json.loads(match.group())
            return [
                ExtractedRequirement(
                    section_key=item.get("section_key", "extracted"),
                    requirement_text=item.get("requirement_text", ""),
                    priority=item.get("priority", "normal"),
                )
                for item in items
                if item.get("requirement_text")
            ]
    except Exception as exc:
        logger.warning("LLM requirement extraction failed: %s, falling back to stub", exc)

    return _extract_requirements_stub(chunks_text)
