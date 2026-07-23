# Retrieval + Content-plan + Outline editor

Date: 2026-07-23

## Product goal

Close the three remaining OpenBidKit-parity gaps after approve→export:

1. **Evidence binding** — section drafts must attach Chinese knowledge chunks
2. **Content-plan before draft** — structure tables/figures/key points before body generation
3. **Outline visual editor** — add/rename/reorder/remove chapters on the project page

## Root cause: evidence_count=0

Workflow query was:

```python
query = section_key.replace("-", " ")  # "technical approach"
```

Against Chinese knowledge corpora this yields:

- FTS bigrams that never appear as document lexemes on raw `retrieval_text`
- Trigram similarity against the full bilingual string ≈ 0

Even after expanding to Chinese keywords, trigram used the **entire multi-keyword string** as one phrase (`ilike %技术方案 架构 微服务%`), which never matches.

## Fixes

### 1. Section query expansion

- New: `services/worker/app/retrieval/section_query.py`
- `expand_section_retrieval_query("technical-approach")` → bilingual lexical query
- `section_fallback_query(...)` pure Chinese domain terms when primary returns empty
- Wired into LangGraph `knowledge_retriever` and legacy `execution/drafting`

### 2. Trigram multi-term matching

- `packages/contracts/retrieval_repository.py`
- Split whitespace-delimited keywords and OR phrase/`%` matches
- Expanded Chinese queries now hit via trigram (and FTS when `retrieval_text` is normalized)

### 3. Content-plan node

- New node: `services/worker/app/graph/nodes/content_plan.py`
- Graph path: `knowledge_retriever → content_plan → section_drafter`
- Deterministic (no extra model call): outline, key points, evidence picks, table/figure suggestions, gaps
- Injected into drafter system prompt
- Re-plan on quality fail / human rejection clears stale draft state

### 4. Outline editor

- Migration `ad3e4f5b6c7d`: `deliverable_section.sort_order`
- API: create/update/reorder/delete section endpoints
- UI: project detail tab **大纲** (`OutlineEditorTab`) with add / rename / up-down reorder / delete

## Verification

| Check | Result |
|---|---|
| Worker focused tests (retrieval, content-plan, supervisor, graph, drafter) | ✅ **47 passed** |
| Live smoke DB: expanded query on Chinese chunk | ✅ FTS + trigram hit |
| Web `tsc --noEmit` | ✅ |
| Alembic upgrade smoke + test DBs | ✅ `ad3e4f5b6c7d` |

## Files

**Worker / contracts**

- `services/worker/app/retrieval/section_query.py`
- `services/worker/app/graph/nodes/knowledge_retriever.py`
- `services/worker/app/graph/nodes/content_plan.py`
- `services/worker/app/graph/nodes/section_drafter.py`
- `services/worker/app/graph/nodes/supervisor.py`
- `services/worker/app/graph/builder.py`
- `services/worker/app/graph/state.py`
- `services/worker/app/execution/drafting.py`
- `packages/contracts/retrieval_repository.py`
- `packages/contracts/models.py` (`sort_order`)

**API / Web**

- `services/api/alembic/versions/ad3e4f5b6c7d_add_deliverable_section_sort_order.py`
- `services/api/app/deliverables/{schemas,repository,service,router}.py`
- `apps/web/src/features/projects/tabs/outline-editor-tab.tsx`
- `apps/web/src/features/projects/project-detail-page.tsx`
- `apps/web/src/lib/api.ts`
- i18n `tabs.outline`

## Note on seeded chunks

Ad-hoc SQL seeds that set `retrieval_text = content` (raw Chinese) miss FTS until re-normalized. Production ingest already writes `normalize_retrieval_text(content)`. Trigram multi-term still recovers evidence on raw content.

## Bottom line

Main writing loop is now:

`outline edit → retrieve (CN-aware) → content plan → draft → HITL approve → export`
