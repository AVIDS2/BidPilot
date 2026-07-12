# Agent Engineering Glossary

This is a living glossary. Each entry should eventually link to a BidPilot implementation, test, trace, or evaluation.

| Term | Plain-language meaning | BidPilot meaning |
| --- | --- | --- |
| Workflow | A mostly known sequence of steps | Parse tender -> retrieve evidence -> draft -> review -> persist |
| Agent | A model-driven loop that chooses its next action | Assistant decides which platform tool or workflow to invoke |
| Harness | The runtime wrapper around the model, tools, state, and policies | Tool registry, context pack, approval policy, event stream, and loop limits |
| ReAct | Reasoning/action/observation loop | Select tool, execute it, inspect result, continue or finish |
| Tool calling | Model emits a typed request for an external capability | Search projects, import files, start drafting, export deliverables |
| Orchestrator-worker | One planner fans work out to specialized workers and merges results | Split document extraction or section drafting across workers |
| HITL | Human-in-the-loop approval or correction | Approve destructive actions and high-impact generated content |
| Checkpointer | Durable snapshots of one execution thread | Resume a conversation or workflow after interruption |
| Store | Cross-thread application memory | User/org/project preferences and validated facts |
| Working memory | Context needed for the current turn | Current project, plan, tools, pending approval, recent messages |
| Episodic memory | What happened in previous tasks | Run outcomes, review decisions, failed attempts, corrections |
| Semantic memory | Stable facts and concepts | Tender requirements, company capabilities, customer facts |
| Procedural memory | Reusable ways of doing work | Organization playbooks, writing rules, approval policies |
| Dense retrieval | Search by embedding similarity | Find semantically related evidence chunks |
| Sparse retrieval | Search by exact terms or lexical matching | Match acronyms, legal phrases, model numbers, and names |
| Hybrid retrieval | Fuse dense and sparse search | Combine pgvector and PostgreSQL full-text results |
| RRF | Rank fusion that combines result lists | Merge dense and sparse candidates before reranking |
| Reranker | A second model that scores query-document pairs | Improve evidence precision after broad recall |
| Context compression | Reduce retrieved material to useful facts | Keep the prompt small while preserving citations |
| Grounding | Tie a generated claim to a source | Every important bid claim links to source document/page/chunk |
| Trace | End-to-end record of an agent invocation | User request -> model -> tool -> workflow -> output |
| Span | One timed operation inside a trace | Retrieval, rerank, model call, tool call, or DB write |
| Eval | A repeatable quality measurement | Retrieval recall, tool accuracy, citation faithfulness, task success |
| SLO | Reliability target for a service | P95 assistant latency, workflow completion, approval safety |
