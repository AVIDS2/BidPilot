# BidPilot Product IA and Memory Control Plane

- Status: ready for staged implementation
- Date: 2026-09-09
- Owner: product/runtime/frontend collaboration
- Canonical architecture: `docs/superpowers/specs/2026-07-17-bidpilot-governed-memory-wiki-design.md`
- Canonical UX rules: `docs/product/frontend-experience-principles.md`
- Canonical terminology: `docs/product/domain-glossary.md`

## Problem

The current workbench exposes implementation-shaped surfaces: project facts,
Agent runs, inbox items, knowledge compilation, project memory, and Mem0 are
visible as if they were peer products. Users cannot tell whether an item is a
project fact, a task to act on, a past event, a personal preference, or an
internal runtime status.

The backend already has most of the control-plane primitives, but the product
surface and the four-memory model are not aligned. The implementation must
therefore converge the information architecture before adding more AI features.

## Decisions

### Product navigation

Keep the primary workbench focused on:

- `总览`
- `项目`
- `我的工作`
- `助手`

Move project-specific work into project tabs: `概览`, `资料`, `要求`, `响应`,
`审核`, `交付`, and `项目知识`.

Make `运行记录` admin/recovery-only. Fold ordinary inbox items into `我的工作`
and notifications. Keep `知识库` as a cross-project source-backed knowledge
index, but do not expose “memory compilation” as the user's mental model.

### Memory model

| User term | Engineering type | Implementation source |
| --- | --- | --- |
| 当前工作上下文 | Working memory | Pi session + conversation/runtime state |
| 工作记录 | Episodic memory | ChatMessage, RuntimeRun/Event, reviews, audit |
| 项目知识 | Semantic memory | approved `MemoryRecord` + evidence links |
| 团队方法 | Procedural memory | published org/project knowledge and Skills |
| 用户偏好 | personalization, not business memory | Mem0 + local sync/privacy ledger |

### Mem0 boundary

Mem0 receives bounded successful-turn user/assistant messages only for stable,
low-risk preferences. It is queried additively before a Pi turn and fails open.
It never stores tender facts, files, deadlines, quotes, qualifications,
credentials, tool envelopes, or hidden reasoning. Account deletion must remove
both the user and user-scoped assistant entity records.

## Implementation Tasks

### P0-A: navigation and page ownership

- [ ] Add a product-owned route map with primary, project, settings, and admin
  ownership.
- [x] Remove `/runs` from ordinary sidebar navigation; preserve deep links and
  expose recovery links only from failed/interrupted business objects.
- [x] Remove ordinary `/inbox` from the primary sidebar; the route remains a
  compatibility/recovery surface until its attention items are merged into
  `我的工作`.
- [x] Add a project workspace tab bar and make project links preserve project and
  section context.
- [x] Replace generic “open Agent” links with contextual action labels such as
  `继续起草`, `查看待审核`, `补齐资料`, or `打开当前项目助手`.

### P0-B: personal memory control

- [x] Add `设置 > 个性化与记忆` with the global personal-memory toggle.
- [x] Add API read/delete endpoints for user-private memory preferences; do not
  proxy raw Mem0 payloads directly to the browser.
- [ ] Add local ledger fields for capture status, last recalled time, deletion
  status, and provider scope without storing message bodies.
- [x] Add clear-all personal preference deletion with an explicit partial-failure
  state. Worker retry integration remains a follow-up.
- [x] Add browser acceptance coverage for off/on, list, and single delete.
  Clear-all and Mem0-disabled browser coverage remain a follow-up.

The first implementation slice is deliberately limited to the control surface
and the existing local memory ledger. Provider-side records are read through a
bounded adapter and deleted only after scope validation; the browser never
receives raw Mem0 responses.

### P0-C: project knowledge review

- [x] Rename user-facing `编译项目记忆` to `整理项目知识` or `生成知识建议`.
- [x] Show proposed/active/rejected records with source citations and reviewer.
  The first project-page slice shows proposed/active records and citations.
- [ ] Add approve, reject, edit, supersede, expiry, and source drill-down flows.
- [ ] Keep graph extraction behind an advanced project action; graph proposals
  never become facts without review.
- [ ] Add a project knowledge detail view; the current portfolio cards alone do
  not provide enough inspectability.

### P1-A: episodic and procedural memory

- [ ] Create a user-facing `工作记录` projection from completed runs, review
  decisions, failed attempts, and corrections. Do not expose raw event logs.
- [ ] Define procedural assets with owner, version, scope, status, and archive
  lifecycle. Skills may be linked as implementation resources but are not
  silently presented as business truth.
- [ ] Add retrieval labels showing whether a result came from evidence, project
  knowledge, team method, or personal preference.

### P1-B: evaluation and observability

- [ ] Add cross-scope leakage tests for user, project, organization, and Mem0
  entity filters.
- [ ] Add memory recall trace fields: memory type, record id, scope, score,
  citation count, and degraded reason; never store provider secrets or raw
  prompts in the user surface.
- [ ] Add five golden questions for each memory type and measure precision,
  stale-memory suppression, deletion effectiveness, and citation faithfulness.
- [ ] Add production counters for Mem0 submitted/succeeded/failed/deleted and
  project proposed/active/rejected records.

## Delivery order

1. Freeze terminology and route ownership in the shared docs.
2. Build the personal memory control surface and API contract.
3. Make project knowledge reviewable and source-linked.
4. Collapse ordinary operations pages into `我的工作` and project tabs.
5. Add episodic/procedural projections and evaluation fixtures.
6. Run local full-stack acceptance, then promote to public staging and production.

## Non-goals

- Do not add Neo4j or another graph database.
- Do not expose Mem0 as a user-facing provider setting.
- Do not auto-activate project or organization facts from model output.
- Do not build a second shadow memory database beside PostgreSQL.
- Do not make Agent chat the only path to inspect or change business data.

## Acceptance Scenarios

1. A user turns personal preference memory off; existing preferences remain
   visible but are not recalled or extended, while project work continues.
2. A user deletes one preference; it disappears from future context packs and the
   provider cleanup ledger reaches a terminal result.
3. A reviewer approves a project fact; the record becomes active with citations
   and appears in the project knowledge view.
4. A reviewer rejects a proposal; it cannot enter future Agent context.
5. A user opens `我的工作` and sees actionable items without seeing runtime
   queue internals or raw event records.
6. A response draft cites project evidence even when personal preference memory
   is present; preference memory never upgrades an unsupported fact.
