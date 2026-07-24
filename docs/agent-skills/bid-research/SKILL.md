---
name: bid-research
description: Research external sources for a bid project, download useful pages into the project, and summarize with citations.
---

# Bid research skill

## When to use

User asks to research market/competitor/policy material, or wants external pages stored into a project.

## Tool preference

1. `web_search` — gather candidate URLs (Tavily if configured, else DuckDuckGo fallback)
2. `fetch_url_to_project` — download selected pages into the project bundle (approval may be required)
3. `semantic_search` — only after ingestion finishes; do not claim evidence before parse completes
4. `write_section` / `start_draft_section` — write findings into outline chapters

## Rules

- Prefer official sources and standards over random blogs.
- Always keep source URLs in the tool payload; do not invent citations.
- If upload/parse is still running, say so and wait for wake/notification rather than looping blindly.
- Destructive or costing tools still go through platform approval.
