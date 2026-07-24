# BidPilot Agent Hooks / MCP / Skills Design

Date: 2026-07-24  
Status: implemented skeleton (hooks + background wake + long-task tools)

## Sources

- [shareAI-lab/learn-claude-code](https://github.com/shareAI-lab/learn-claude-code) — s04 hooks, s13 background tasks
- [Claude Code hooks reference](https://code.claude.com/docs/en/hooks)
- [Stop-hook auto-continue pattern](https://agentic-patterns.com/patterns/stop-hook-auto-continue-pattern/)

## Principles

1. **Hook around the loop, never rewrite the loop.**  
   `StreamingHarness.run` stays the single tool-calling loop. Hooks only observe / gate / inject.
2. **Slow work leaves the chat turn.**  
   Draft/export workflows run in Celery/worker; completion publishes a durable wake signal.
3. **Governed side effects only through `execute_capability`.**  
   MCP / skills never bypass approval, quota, tenant scope, audit.
4. **Thin product surface.**  
   No Vercel AI SDK / CopilotKit. OpenAI-compatible tools + our runtime events + React transcript.

## Architecture

```
User message
   │
   ▼
UserPromptSubmit hooks
   │
   ▼
StreamingHarness loop
   ├─ model stream
   ├─ PreToolUse hooks ── block? → tool error message
   ├─ execute_capability (approval / quota / audit)
   ├─ PostToolUse hooks
   ├─ TurnEnd hooks
   └─ Stop hooks ── force-continue reason? → next step
   │
   ▼
Long workflow child RuntimeRun (background)
   │
   ▼
worker complete/fail → Notification(type=agent_task) + optional in-memory bg queue
   │
   ▼
Next user turn / wake path injects <task_notification>
```

## Implemented now

| Piece | Location | Notes |
|-------|----------|-------|
| Hook registry | `services/api/app/runtime/hooks.py` | UserPromptSubmit / PreToolUse / PostToolUse / TurnEnd / Stop / TaskCompleted |
| Background tracker | `services/api/app/runtime/background_tasks.py` | in-process queue + durable Notification helper |
| Harness wiring | `services/api/app/runtime/harness_loop.py` | inject wake notes; Pre/Post/Stop/TurnEnd |
| Workflow wake | `services/worker/app/runtime/events.py` | Notification on run complete/fail |
| Long-task tools | `web_search`, `fetch_url_to_project`, real `upload_document`, `semantic_search` | capability registry + schemas |

## MCP design (product)

Expose BidPilot capabilities as an **internal MCP server** later, not a second agent:

- Transport: local stdio for CLI / HTTP for workspace tools
- Tools: mirror `CAPABILITY_REGISTRY` names exactly
- Auth: service token + user JWT; still call `execute_capability`
- Resources: project outline, readiness summary, latest run events
- Prompts: outline-first drafting, export readiness, review queue triage

**Do not** let external MCP tools write domain tables directly.

## Skills design

Project skills live under `docs/agent-skills/` (markdown SKILL.md style):

1. `bid-outline-first` — always outline → section_key → write/draft  
2. `bid-evidence-first` — require semantic_search before factual claims  
3. `bid-export-ready` — readiness gaps → approve sections → export  
4. `bid-research` — web_search → fetch_url_to_project → summarize with citations  

Skills are **prompt packs + tool preference**, not new engines.

## Hooks design (self-sensing)

| Event | BidPilot use |
|-------|----------------|
| UserPromptSubmit | inject pending wake notes / active project |
| PreToolUse | optional deny list, rate limits, duplicate-call guard |
| PostToolUse | metrics, memory candidates, transcript enrichment |
| Stop | force-continue if criteria unmet (tests / incomplete plan) |
| TaskCompleted | worker finished draft/export; wake conversation |

Wake UX (next):

1. Notification bell shows `agent_task`  
2. Opening `/agent?conversation=…&wake=…` loads conversation and injects task_notification  
3. Optional auto-continue turn when user preference `agent.auto_resume=true`

## Failure recovery (multi-step)

Already in harness:

- tool error returned to model (compact public error)
- consecutive failure circuit breaker (3)
- max_steps hard ceiling

Added:

- Stop-hook force-continue budget (one retry path when registered)
- wake notifications so long workflow completion is not “forgotten”

## Out of scope for this slice

- Full MCP server process
- Auto-resume without user open (needs push/SSE fanout product decision)
- Arbitrary shell / computer-use tools
- YOLO mode for destructive tools

## Verification

- unit: registry formatters for new tools
- local smoke: web_search (DuckDuckGo fallback), search_projects, pending delete path
- public deploy: api/worker rebuild when ready
