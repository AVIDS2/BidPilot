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


def select_skill_names(_user_message: str = "", *, max_skills: int = 2) -> list[str]:
    """Return the bounded skill set available to the model this turn.

    Skill activation is intentionally model-driven. The runtime never routes
    on user-message fragments, trigger tables, or lexical similarity.
    """
    del max_skills
    return [skill.name for skill in build_skill_index()]


def build_skill_index_block() -> str:
    """Level-1 availability block injected once per turn (name + description)."""
    index = build_skill_index()
    if not index:
        return ""
    lines = ["AVAILABLE_SKILLS:", "The following skills may help. Read the selected skill body only when relevant."]
    lines.extend(skill.to_index_line() for skill in index)
    return "\n".join(lines)


def build_skill_prompt_block(user_message: str) -> str:
    """Return the model-visible skill bodies without message-based routing."""
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
