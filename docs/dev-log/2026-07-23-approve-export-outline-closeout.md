# Approve → Export + Outline-first closeout

Date: 2026-07-23

## Product goal

Match OpenBidKit's practical bid-writing loop while keeping BidPilot's governed SaaS control plane:

1. **Outline-first**: project scenario sections are a first-class outline with progress
2. **Draft one section at a time** through LangGraph
3. **HITL approve**
4. **Export partial package** of approved section bodies (DOCX/PDF)

## Code changes

### Export / approval path

- `persist_result_node` promotes `DeliverableSection.status` to `approved` when `human_decision == "approved"`
- Recomputes deliverable status:
  - all non-empty sections approved → deliverable `approved`
  - some approved → `in_review`
- Replay path also promotes status (covers resume re-entry)
- Export allows partial packages when approved section content exists
  - HTTP: `GET /export/deliverables/{id}/docx|pdf`
  - Assistant: `export_deliverable`

### Outline-first agent capability

- Enhanced `list_sections` with version/content progress
- New capability `get_project_outline`:
  - scenario template order
  - drafted/approved counts
  - missing vs existing sections
- Registered in capability registry + harness tool schema

## Live DeepSeek evidence

Environment: API `:8001`, worker solo, DB `docpilot_smoke`, model `deepseek-chat`.

| Step | Result |
|---|---|
| Create project with bidpilot outline (5 sections) | ✅ |
| Seed knowledge chunk | ✅ |
| Assistant `get_project_outline` | ✅ tool call + summary |
| Assistant `start_draft_section` technical-approach | ✅ |
| LangGraph draft → HITL `awaiting_human` | ✅ |
| Resume approved → persist section version | ✅ |
| Section review/export readiness | ✅ section `approved` |
| `GET .../export/.../docx` | ✅ **37542 bytes** |
| `GET .../export/.../pdf` | ✅ **5418 bytes** |
| Assistant `export_deliverable` | ✅ `download_path` returned |

Artifacts:

- `tmp/e2e-export.docx`
- `tmp/e2e-export.pdf`
- `tmp/e2e-full-report.json`
- `tmp/e2e-outline2.sse.txt`
- `tmp/e2e-export.sse.txt`

## OpenBidKit parity assessment

| OpenBidKit behavior | BidPilot now |
|---|---|
| Directory/outline before body | `get_project_outline` + scenario default sections |
| Section-by-section writing | LangGraph per `section_key` |
| Human finalize before ship | HITL + section approval gate for export |
| Export package | DOCX/PDF from approved section bodies |
| Durable long jobs | RuntimeRun + Outbox + Postgres checkpoint |
| Knowledge-bound writing | KnowledgeChunk/Evidence path (retrieval quality still improvable) |

Not yet OpenBidKit-complete (next product slices):

- explicit content-plan node (tables/figures/knowledge picks before draft)
- multi-section batch orchestration with progress board UX
- richer outline editing UI (add/remove/reorder chapters)
- stronger retrieval for ad-hoc seeded chunks (`evidence_count` still often 0)

## Bottom line

The **real agent path users care about** is now runnable:

`outline → draft section → human approve → export DOCX/PDF`

with DeepSeek, streaming harness, and LangGraph HITL.
