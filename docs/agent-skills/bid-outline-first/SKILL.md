---
name: bid-outline-first
description: Always resolve outline section_key before drafting or writing chapter content.
---

# Outline-first drafting skill

## When to use

Any request to write, draft, rewrite, or generate bid chapters / executive summary.

## Tool preference

1. `get_project_outline` or `list_sections`
2. Pick concrete `section_key` from tool payload (never invent)
3. No materials → `write_section`
4. Has materials → `start_draft_section` (optionally after `semantic_search`)
5. Review / export only after content exists

## Rules

- If outline tools return empty keys, create deliverable / wait for template sections first.
- Do not dump long draft only in chat; persist to a section.
- Same-name projects must use `id` / `short_id`.
