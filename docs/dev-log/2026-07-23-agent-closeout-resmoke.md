# Agent closeout re-smoke + UI converge

Date: 2026-07-23

## Goal

Close the three remaining product-confidence gaps after OpenBidKit-parity slices:

1. DeepSeek full-path re-smoke with Chinese evidence + content-plan
2. Browser / UI golden-path readiness for outline → draft → approve → export
3. Assistant transcript L1 convergence (single i18n path + multi-tool turn aggregation)

## DeepSeek full-path evidence

Stack: API `:8001`, worker solo, DB `docpilot_smoke`, model `deepseek-chat`.

Working provider key came from **process/user env** (suffix `27b0`).  
`services/api/.env` DeepSeek key suffix `9a49` is still invalid and must not override the process env.

| Step | Result |
|---|---|
| Outline API create / rename / reorder | ✅ |
| Seed Chinese knowledge chunk | ✅ |
| Retrieve with bilingual expansion | ✅ `evidence_count=1` |
| Content-plan node | ✅ worker log `Content plan ... evidence=1 key_points=3` |
| Section draft via DeepSeek | ✅ `model_used=deepseek-chat` |
| HITL `awaiting_human` → approve | ✅ |
| Persist section/deliverable approved | ✅ |
| Export DOCX | ✅ **37614 bytes** |
| Export PDF | ✅ **2866 bytes** |
| Assistant `export_deliverable` | ✅ `download_path` present |

Artifacts:

- `tmp/closeout-report.json`
- `tmp/closeout-export.docx`
- `tmp/closeout-export.pdf`
- `tmp/closeout-export.sse.txt`
- `tmp/closeout-outline.sse.txt`
- `tmp/closeout-draft.sse.txt`

Run proof:

- `project_id`: `8b6cb462-581a-478f-a9e8-2adb57f71ecc`
- `run_id`: `737c69b2-3184-48da-aabe-26d70f9c30ed`
- `section_version_id`: `7d4402d0-47fc-4aff-9ebd-c119774effea`

## UI converge

- `assistant-activity-timeline` now:
  - keeps **single-tool** L1 on existing i18n contract (`Search projects running` / `Open page completed`)
  - uses **transcript aggregation** for multi-tool / multi-turn L1
  - labels new workflow nodes: `content_plan`, `knowledge_retriever`, `human_approval`, `persist_result`
- Tests: assistant transcript + panel **27 passed**
- Web `tsc --noEmit` clean

## Browser golden path

Code path is present:

- Project detail tab **大纲** → `OutlineEditorTab`
- Drafting / review / export tabs already wired

Authenticated browser walkthrough needs web pointed at smoke API:

```bash
VITE_API_URL=http://127.0.0.1:8001 pnpm --dir apps/web exec vite --host 127.0.0.1 --port 5174
```

Default Vite on `:5173` still falls back to `http://localhost:8000`.

## Provider gotcha

Do **not** let `.env` clobber a working `DEEPSEEK_API_KEY` from the user/process environment.  
Smoke launcher `tmp/start_smoke_stack.py` now preserves process env secrets and forces drafting onto DeepSeek via `LLM_API_*`.

## Bottom line

```text
outline edit → CN-aware retrieve → content-plan → DeepSeek draft → HITL approve → export
```

is proven again on the live local smoke stack with real artifacts.

## Closeout decision

**Close agent main-path work for this arc.**

Treat as:

- **Agent MVP / controlled pilot: CLOSED**
- **Release-ready product package: NOT claimed**

Next session should start from release hardening (clean rehearsal, browser
recording, provider env hygiene), not from reopening the main writing loop
unless a regression appears.
