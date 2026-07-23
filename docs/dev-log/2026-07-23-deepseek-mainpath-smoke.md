# Local DeepSeek main-path smoke

Date: 2026-07-23

## Environment

- Clean DB: `docpilot_smoke` at Alembic head `ac2d3e4f5b6c`
- API: `http://127.0.0.1:8001` (`DOCPILOT_ASSISTANT_STREAMING_HARNESS=true`, `USE_LANGGRAPH=1`)
- Worker: Celery solo pool, PostgresSaver ready, BidPilot graph compiled
- Model: DeepSeek `deepseek-chat` via OpenAI-compatible endpoint
- Note: `services/api/.env` DeepSeek key suffix `9a49` is invalid; User env key suffix `27b0` works

## Harness HTTP smoke

### 1. Plain answer
Request: `1+1=?`  
Events: `start → turn_started → message deltas → end(completed)`  
Final text: includes `**2**`

### 2. Tool loop
Request: search projects  
Events: `tool_started(search_projects) → tool_succeeded(count=0) → turn_finished → turn_started → summary → end`  
Final text: no projects yet (empty smoke DB at that moment)

## Workflow main path

1. Create project `DeepSeek烟雾项目`
2. Seed bundle + source_document + knowledge_chunk
3. Assistant harness with `approval_mode=full_access` called `start_draft_section`
4. Worker executed `draft_section via LangGraph`
5. DeepSeek draft + quality review completed
6. Run status: **`awaiting_human`**
7. `POST /drafting/runs/{id}/resume` with `decision=approved`
8. Worker `resume_draft via LangGraph` → human approval resolved → **persisted**
9. Final execution status: **`succeeded`**
   - `section_version_id`: `f6509956-92c0-49e8-8a2d-37f412ee77ce`
   - `model_used`: `deepseek-chat`
   - `iterations`: 1

## LangGraph alignment verified live

- Dynamic `interrupt()` HITL pause ✅
- `Command(resume=...)` resume ✅
- Postgres checkpointer ✅
- Product runtime events + outbox delivery ✅

## Open issues observed

1. Main `docpilot` DB alembic drift (subscription table present while version lagging) — use smoke DB or stamp carefully
2. Retrieval returned `evidence_count=0` despite seeded chunk (embedding/profile path still weak for ad-hoc seed)
3. Worker Windows spawn needs `-P solo` or named `task_on_failure` (lambda pickle fixed)
4. Do not source invalid DashScope keys over a good DeepSeek key when starting worker

## Bottom line

Product main path is now proven locally with DeepSeek:

`assistant harness tool call → LangGraph draft → HITL → resume → persist`
