"""Standard Agent Skills loader for the governed harness.

Follows the progressive-disclosure model from Anthropic's Agent Skills spec
and the AI-Agents-in-Depth chapter on skills:

  Level 1 (metadata, always loaded):
    Every ``docs/agent-skills/<name>/SKILL.md`` frontmatter is scanned into a
    ``SkillIndex`` (name + description, ~100 tokens each).  The index is
    injected once per turn as ``AVAILABLE_SKILLS`` so the model can route on
    ``description`` ("when to use me") without consuming full bodies.

  Level 2 (instructions, loaded explicitly):
    The model calls ``read_skill`` with an exact name from ``AVAILABLE_SKILLS``.
    The cached, compacted body is then returned as a tool observation.

  Level 3 (resources / scripts):
    Bundled files are referenced by the body; they are read on demand by the
    tools the skill prescribes.  No token cost until accessed.

Skill selection is model-driven. The base prompt only exposes metadata and the
model must explicitly call ``read_skill`` before a procedure enters context.
The runtime never routes skills by matching words in the user's message.
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


def select_skill_names(
    requested_names: str | list[str] | tuple[str, ...] | None = None,
    *,
    max_skills: int = 2,
) -> list[str]:
    """Validate explicitly requested skill names without inspecting user text."""
    if requested_names is None:
        return []
    requested = [requested_names] if isinstance(requested_names, str) else list(requested_names)
    available = set(list_skill_names())
    selected: list[str] = []
    for raw_name in requested:
        name = str(raw_name or "").strip()
        if name in available and name not in selected:
            selected.append(name)
        if len(selected) >= max(1, max_skills):
            break
    return selected


def build_skill_index_block() -> str:
    """Level-1 availability block injected once per turn (name + description)."""
    index = build_skill_index()
    if not index:
        return ""
    lines = [
        "AVAILABLE_SKILLS:",
        "Select the skill whose declared scope fits the current goal. Call read_skill(name) before following it; do not invent its contents.",
    ]
    lines.extend(skill.to_index_line() for skill in index)
    return "\n".join(lines)


def read_skill(skill_name: str) -> str:
    """Return one allowlisted server-owned Skill body for model context."""
    names = select_skill_names(skill_name, max_skills=1)
    return _read_skill_body(names[0]) if names else ""


def build_skill_prompt_block(skill_names: list[str] | tuple[str, ...] | None = None) -> str:
    """Return bodies only for explicit names; retained for tests and replay."""
    names = select_skill_names(skill_names)
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
    "read_skill",
    "select_skill_names",
]
