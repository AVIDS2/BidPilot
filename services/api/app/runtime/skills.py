"""Load project agent skills (markdown SKILL.md packs) for harness injection.

Skills are prompt packs + tool preference, not a second engine. Matching is
keyword-based and intentionally conservative so we never flood every turn.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

# BidPilot repo root: services/api/app/runtime/skills.py -> parents[4]
_ROOT = Path(__file__).resolve().parents[4]
_SKILLS_DIR = _ROOT / "docs" / "agent-skills"

_SKILL_TRIGGERS: dict[str, tuple[str, ...]] = {
    "bid-outline-first": (
        "起草",
        "拟草",
        "章节",
        "大纲",
        "write_section",
        "start_draft",
        "执行摘要",
        "全部章节",
        "多章节",
        "整本",
        "campaign",
        "section",
        "draft",
        "outline",
    ),
    "bid-research": (
        "研究",
        "调研",
        "联网",
        "web_search",
        "检索资料",
        "政策",
        "竞品",
        "fetch_url",
        "research",
        "search the web",
    ),
}


@lru_cache(maxsize=16)
def _read_skill_body(skill_name: str) -> str:
    path = _SKILLS_DIR / skill_name / "SKILL.md"
    if not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    # Drop YAML frontmatter if present.
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            text = parts[2]
    # Keep the pack compact for system prompt budget.
    lines = [line.rstrip() for line in text.strip().splitlines()]
    compact: list[str] = []
    for line in lines:
        if not line.strip():
            if compact and compact[-1] != "":
                compact.append("")
            continue
        compact.append(line)
        if sum(len(item) for item in compact) > 1200:
            compact.append("…")
            break
    return "\n".join(compact).strip()


def select_skill_names(user_message: str, *, max_skills: int = 2) -> list[str]:
    text = (user_message or "").strip()
    if not text:
        return []
    lowered = text.casefold()
    hits: list[str] = []
    for name, triggers in _SKILL_TRIGGERS.items():
        if any(trigger in text or trigger.casefold() in lowered for trigger in triggers):
            hits.append(name)
        if len(hits) >= max_skills:
            break
    return hits


def build_skill_prompt_block(user_message: str) -> str:
    """Return an optional system-prompt appendix with matched skills."""
    names = select_skill_names(user_message)
    if not names:
        return ""
    chunks: list[str] = ["## Active project skills (follow when relevant)"]
    for name in names:
        body = _read_skill_body(name)
        if not body:
            continue
        chunks.append(f"### skill:{name}\n{body}")
    if len(chunks) == 1:
        return ""
    return "\n\n".join(chunks)


def clear_skill_cache() -> None:
    _read_skill_body.cache_clear()


__all__ = [
    "build_skill_prompt_block",
    "clear_skill_cache",
    "select_skill_names",
]
