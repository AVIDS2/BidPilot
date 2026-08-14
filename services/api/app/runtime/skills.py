"""Standard Agent Skills loader for the governed harness.

Follows the progressive-disclosure model from Anthropic's Agent Skills spec
and the AI-Agents-in-Depth chapter on skills:

  Level 1 (metadata, always loaded):
    Every ``docs/agent-skills/<name>/SKILL.md`` frontmatter is scanned into a
    ``SkillIndex`` (name + description, ~100 tokens each).  The index is
    injected once per turn as ``AVAILABLE_SKILLS`` so the model can route on
    ``description`` ("when to use me") without consuming full bodies.

  Level 2 (instructions, loaded when triggered):
    ``build_skill_prompt_block`` reads the matched SKILL.md body (cached,
    compacted) and appends it as ``SELECTED_PROCEDURAL_SKILLS``.

  Level 3 (resources / scripts):
    Bundled files are referenced by the body; they are read on demand by the
    tools the skill prescribes.  No token cost until accessed.

Matching stays deterministic and conservative: it runs against the
``description`` (the routing contract), never against arbitrary user text, so
untrusted input cannot silently flip a skill on.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

# BidPilot repo root: services/api/app/runtime/skills.py -> parents[4]
_ROOT = Path(__file__).resolve().parents[4]
_SKILLS_DIR = _ROOT / "docs" / "agent-skills"

# Fallback triggers only used when a SKILL.md has no parseable frontmatter.
# New skills should declare their own description; this table keeps the two
# existing packs stable while the loader is upgraded.
_LEGACY_TRIGGERS: dict[str, tuple[str, ...]] = {
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


@dataclass(frozen=True)
class SkillMetadata:
    """Level-1 discovery record for one skill."""

    name: str
    description: str
    path: Path

    def to_index_line(self) -> str:
        return f"- {self.name}: {self.description}"


def _parse_frontmatter(text: str) -> dict[str, str]:
    """Parse the YAML frontmatter block of a SKILL.md.

    Only ``name`` and ``description`` are required by the spec; unknown keys
    are ignored so third-party skills keep their extras.  Returns {} when the
    file has no ``---`` fence or the frontmatter cannot be read.
    """
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    fm = parts[1]
    fields: dict[str, str] = {}
    for line in fm.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^([A-Za-z][A-Za-z0-9_-]*)\s*:\s*(.*)$", line)
        if not m:
            continue
        key = m.group(1).strip()
        value = m.group(2).strip().strip("\"'")
        if key in {"name", "description"} and value:
            fields[key] = value
    return fields


@lru_cache(maxsize=1)
def build_skill_index() -> list[SkillMetadata]:
    """Scan ``_SKILLS_DIR`` for skills; returns Level-1 metadata records."""
    index: list[SkillMetadata] = []
    if not _SKILLS_DIR.is_dir():
        return index
    for entry in sorted(_SKILLS_DIR.iterdir()):
        if not entry.is_dir():
            continue
        skill_md = entry / "SKILL.md"
        if not skill_md.is_file():
            continue
        try:
            text = skill_md.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        fm = _parse_frontmatter(text)
        name = fm.get("name") or entry.name
        description = fm.get("description") or "No description provided."
        index.append(SkillMetadata(name=name, description=description, path=skill_md))
    return index


def list_skill_names() -> list[str]:
    """Names of every discovered skill (for tests / diagnostics)."""
    return [skill.name for skill in build_skill_index()]


@lru_cache(maxsize=16)
def _read_skill_body(skill_name: str) -> str:
    """Read one SKILL.md body (Level 2) without the frontmatter, compacted."""
    for skill in build_skill_index():
        if skill.name == skill_name:
            path = skill.path
            break
    else:
        path = _SKILLS_DIR / skill_name / "SKILL.md"
    if not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    # Drop YAML frontmatter if present.
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            text = parts[2]
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


def _description_keywords(description: str) -> list[str]:
    """Tokenize a skill description for deterministic routing.

    Extracts both English words (>=3 chars) and meaningful Chinese fragments
    (2-4 char runs), since descriptions may be authored in either language.
    Routing stays on the description (the spec's routing contract) without
    invoking an LLM per turn.
    """
    lowered = description.casefold()
    keywords: list[str] = []
    for token in re.findall(r"[a-z0-9][a-z0-9_-]{2,}", lowered):
        if len(token) >= 3:
            keywords.append(token)
    # Chinese runs: split into 2-4 char fragments so routing tolerates
    # wording variation ("投标" / "投标文件" / "技术标书").
    for run in re.findall(r"[一-鿿]{2,}", description):
        if len(run) <= 4:
            keywords.append(run)
        else:
            for index in range(len(run) - 1):
                fragment = run[index : index + 2]
                if fragment not in keywords:
                    keywords.append(fragment)
    return keywords


def select_skill_names(user_message: str, *, max_skills: int = 2) -> list[str]:
    """Return skill names whose description matches the user message.

    Matching runs against ``description`` (the standard routing signal) plus a
    legacy Chinese-trigger fallback for existing packs.  Skills are ranked by
    how many description keywords hit, so a more specific skill (e.g. the
    tender writer) wins over a generic one (e.g. outline-first) when both
    could apply.  Both signals are conservative keyword checks; neither ever
    executes the skill body.
    """
    text = (user_message or "").strip()
    if not text:
        return []
    lowered = text.casefold()
    index = build_skill_index()
    scored: list[tuple[int, int, str]] = []  # (hit_count, index_order, name)
    for order, skill in enumerate(index):
        desc = skill.description.strip()
        score = 0
        if desc and desc.casefold() != "no description provided.":
            score += sum(1 for keyword in _description_keywords(desc) if keyword in lowered)
        # Legacy Chinese/English trigger fallback.
        legacy = _LEGACY_TRIGGERS.get(skill.name, ())
        if any(trigger in text or trigger.casefold() in lowered for trigger in legacy):
            score += 1
        if score > 0:
            scored.append((score, order, skill.name))
    # Highest specificity first; stable tie-break by discovery order.
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [name for _score, _order, name in scored[:max_skills]]


def build_skill_index_block() -> str:
    """Level-1 availability block injected once per turn (name + description)."""
    index = build_skill_index()
    if not index:
        return ""
    lines = ["AVAILABLE_SKILLS:", "The following skills may help. Read the selected skill body only when relevant."]
    lines.extend(skill.to_index_line() for skill in index)
    return "\n".join(lines)


def build_skill_prompt_block(user_message: str) -> str:
    """Return an optional system-prompt appendix with matched skill bodies."""
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
    build_skill_index.cache_clear()


__all__ = [
    "build_skill_index",
    "build_skill_index_block",
    "build_skill_prompt_block",
    "clear_skill_cache",
    "list_skill_names",
    "select_skill_names",
]
