---
name: bid-research
description: Research external sources for a bid project, discover confirmed tender attachments safely, and store only user-approved evidence or artifacts with citations.
---

# Bid research skill

## When to use

User asks to research market/competitor/policy material, find public tender notices
or attachments, or store a user-approved external source in a project.

## Tool preference

### Research text

1. `web_search` — gather candidate URLs (Tavily if configured, else DuckDuckGo fallback).
2. Check that the chosen source is authoritative. For an article or notice body
   the user explicitly wants retained, use `fetch_url_to_project` with
   `import_mode=web_evidence`.
3. `semantic_search` — only after ingestion finishes; do not claim evidence
   before parse completes.
4. `write_section` / `start_draft_section` — write findings into outline chapters.

### Tender attachments

1. Use `web_search` only to locate the public notice page. A search result is
   never proof of an attachment's final download URL.
2. Use `discover_remote_documents` on the chosen public notice page. This is
   read-only: it discovers candidates and must not store or download them.
3. Present filename, source page, direct URL and any content-type hint. Ask the
   user which candidate should be imported; do not select a ZIP/PDF silently.
4. Only after explicit confirmation call `fetch_url_to_project` with
   `import_mode=artifact`. It creates a background, durable import run for
   large attachments.

## Rules

- Prefer official sources and standards over random blogs.
- Always keep source URLs in the tool payload; do not invent citations.
- Never use `fetch_url_to_project` in `artifact` mode against a notice or
  article HTML page. Use `web_evidence` only when the user actually wants the
  webpage body saved as evidence.
- An artifact failure is authoritative. Explain its stable error category and
  offer the matching next action (refresh the final direct link, retry later,
  or download/upload locally). Do not rewrite the URL, switch protocol, or
  repeat the same import without a new user confirmation.
- If upload, import, or parse is still running, say so and wait for the durable
  run event/notification rather than polling or repeatedly asking whether it
  completed.
- Destructive or costing tools still go through platform approval.
