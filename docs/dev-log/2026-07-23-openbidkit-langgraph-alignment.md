# OpenBidKit + LangGraph Design Alignment for BidPilot

Date: 2026-07-23

## Sources

- [OpenBidKit_Yibiao](https://github.com/FB208/OpenBidKit_Yibiao)
- [OpenBidKit AGENTS.md](https://raw.githubusercontent.com/FB208/OpenBidKit_Yibiao/main/AGENTS.md)
- [LangGraph HITL](https://docs.langchain.com/langsmith/add-human-in-the-loop.md)
- [LangGraph checkpointer config](https://docs.langchain.com/langsmith/configure-checkpointer.md)
- [LangGraph SSE protocol v2](https://docs.langchain.com/langsmith/agent-server-api/streaming/protocol-v2-event-stream-sse.md)

## What OpenBidKit does well (borrow ideas, not stack)

OpenBidKit is a **local Electron bid OS**, not a multi-tenant SaaS control plane. Still, its product architecture is strong:

1. **Staged editable pipeline**  
   tender parse → outline → global facts → body plan → body write → expand/audit → illustrations → export  
   Each stage is human-revisable; outline structural change invalidates body cache.

2. **Authority of content**  
   `outlineData.outline[*].content` is the single source of truth for display and export.

3. **Durable background tasks**  
   Parse/generate survive navigation; task state is on disk, not only UI spinner.

4. **Shared agent substrate**  
   OpenCode + Pi share model config, proxy, tools, and a **global serial queue**.

5. **Knowledge as first-class workspace**  
   Company materials → blocks → matched items → selected `item_ids` in body planning. No invented knowledge IDs.

6. **Plan before write**  
   Per-leaf content plan (knowledge / table / mermaid / image) before concurrent section writing.

### BidPilot mapping

| OpenBidKit idea | BidPilot current | Next product move |
|---|---|---|
| Outline → body stages | Section keys + section versions | Keep section as authority; avoid free-form draft-only UX |
| Durable long jobs | RuntimeRun + Outbox + ExecutionRun | Keep; surface progress in assistant transcript |
| Serial agent queue | Harness max_steps + capability policy | Keep single harness as control plane for user intents |
| Knowledge items | KnowledgeChunk + Bid Wiki + Evidence | Prefer evidence/claim IDs only; never invent |
| Plan before write | quality_review + section_drafter loop | Optional future: explicit section plan node before draft |
| Local export | DOCX/PDF export capability | Keep export gated on approval |

**Do not copy:** Electron-only storage, AGPL desktop packaging, dual OpenCode/Pi runtimes as product surface. BidPilot’s SaaS control plane (auth, org, quotas, audit) is the differentiator.

## LangGraph docs check against our drafting graph

### HITL

Docs recommend **dynamic `interrupt()`** inside a node, resume with `Command(resume=...)`.

BidPilot status:

- `human_approval_node` uses `interrupt(payload)` ✅
- `resume_graph` uses `Command(resume={decision, feedback})` ✅
- Assistant can resume via `resume_draft_run` capability ✅
- Docstring previously said `interrupt_before` (static) — corrected to dynamic interrupt ✅

### Checkpointing

Docs: durable checkpointer required for production HITL; Postgres is the standard durable backend.

BidPilot status:

- Worker graph: `PostgresSaver` via `DOCPILOT_LANGGRAPH_CHECKPOINTER` ✅
- Operator (legacy): Postgres checkpointer outside local memory ✅
- Checkpoint tables present on main DB (`checkpoints`, `checkpoint_writes`, …) ✅

### Streaming / UI events

Docs SSE protocol emphasizes channels: `tasks`, `tools`, `updates`, `lifecycle`, `values`.

BidPilot status:

- Product does **not** scrape LangGraph internal SSE as UI source of truth.
- Worker publishes durable `RuntimeEvent` (`capability.*` / node progress / approval) and assistant maps to `assistant.*` SSE.
- This matches our product constraint: redacted, ordered, recoverable events without leaking raw graph internals.

### Production caveats applied

1. Prefer dynamic interrupt over static breakpoints — done.
2. Same `thread_id` on resume — BidPilot uses `execution_run_id` as thread id — done.
3. Interrupt payload JSON-serializable — done (preview truncated).
4. Do not treat in-memory checkpointer as production — enforced outside local.

## Implementation decisions locked for this closeout

1. **Harness = OpenBidKit “agent queue” equivalent** for conversational control: multi-step tools, serial by turn, policy/approval boundary.
2. **LangGraph drafting graph = OpenBidKit long-running content pipeline** for section generation quality loop + HITL.
3. **Requirement Ledger / Evidence / Claims** remain BidPilot’s governance spine (OpenBidKit risk workspace analogue, but server-side and auditable).
4. Keep **two layers**:
   - thin streaming harness (chat + tools)
   - durable workflow graph (draft/review/persist)

## Gaps still open (product, not just code)

- Outline-first commercial UX (directory tree as first-class object before body)
- Explicit “content plan” node before drafting (tables/figures/knowledge picks)
- Full authenticated e2e on a clean DB with worker outbox + DeepSeek
- Main `docpilot` DB alembic version drift (subscription table present while version lagging)

## Bottom line

Borrow OpenBidKit’s **staged, durable, knowledge-bound writing OS** ideas.  
Implement them on BidPilot’s **governed SaaS runtime + LangGraph HITL**, not by cloning the Electron agent shell.
