# Workflow + Harness Main-Path Closeout

## Goal

Close the product main path for:

1. Streaming harness assistant (backend complete + existing UI usable)
2. LangGraph drafting workflow (ingest readiness → draft → quality → HITL resume → export)

## Changes landed

### Harness

- Streaming tool-calling loop remains the default (`DOCPILOT_ASSISTANT_STREAMING_HARNESS=true`)
- Typed confirmation arguments now pass through resume (`EDIT` with `confirmation_text`)
- Consecutive tool failures hard-stop the outer loop
- Draft/redraft/memory-graph tools inherit `provider_config_id` / `reasoning_effort`
- Tool schemas fixed:
  - `start_redraft_section.review_feedback`
  - `export_deliverable.project_id`
  - new `resume_draft_run`
- Export no longer hard-requires model-supplied `project_id`; ownership comes from deliverable access check

### Workflow

- `USE_LANGGRAPH` defaults **on** (`1`) so product drafting uses the full graph, not legacy single-shot
- `section_drafter_node` clears stale `review_result` / `review_passed` / `human_decision` on each new draft revision
- Assistant can resume HITL via `resume_draft_run` → `resume_run_command` → `worker.resume_draft`
- `start_draft_section` preflights that the project has ingested `KnowledgeChunk` rows

## Verification

- `tests/runtime/test_harness_loop.py` + registry/policy tests green
- Worker `test_section_drafter` / `test_supervisor` green
- DeepSeek harness smoke previously green for multi-step tool loop

## Still open for full e2e claim

- Local main DB migrations / API on free port (8000 currently occupied by Signal Diff)
- Authenticated browser golden path with real bundle → draft → approve → export
- Real worker Beat/outbox delivery under local compose with USE_LANGGRAPH default
