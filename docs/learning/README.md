# BidPilot Agent Engineering Learning System

This directory is the durable learning record for building BidPilot into an enterprise-grade agent product.

The goal is not to memorize framework APIs. The goal is to understand why the system is designed this way, implement one capability at a time, measure it, and explain the trade-offs in an interview.

## Source Hierarchy

When sources disagree, use this order:

1. Official framework and provider documentation.
2. Original papers and engineering research.
3. BidPilot's own architecture decisions, tests, traces, and evaluation results.
4. High-quality courses and reference repositories.
5. Blog posts, videos, and example applications.

The current course set is:

- Primary agent-systems course: [Agentic AI System Course](https://github.com/bryanyzhu/agentic-ai-system-course)
- Beginner agent patterns: [Microsoft AI Agents for Beginners](https://github.com/microsoft/ai-agents-for-beginners)
- Runnable experiment catalog: [Awesome LLM Apps](https://github.com/Shubhamsaboo/awesome-llm-apps)
- LLM, RAG, and evaluation foundations: [LLM Course](https://github.com/mlabonne/llm-course)
- Runtime authority: [LangGraph documentation](https://docs.langchain.com/oss/python/langgraph/overview)
- Agent harness reference: [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/)

These repositories are learning inputs, not dependencies that should all be installed into BidPilot.

## Learning Loop

Every meaningful feature follows the same loop:

1. Learn the concept in plain language.
2. Map it to the BidPilot product problem.
3. Inspect the existing implementation and identify the gap.
4. Write the design and the success metrics.
5. Implement the smallest production-shaped slice.
6. Add unit, integration, and quality evaluation coverage.
7. Review the trace, failure modes, cost, and security boundary.
8. Record the decision, vocabulary, and what changed.

Natural-language coding is still allowed, but it must start from a written goal and end with evidence.

## Curriculum

### 0. Software and Product Foundations

Learn the existing FastAPI, React, PostgreSQL, Celery, Redis, MinIO, and Docker boundaries. Understand control plane versus execution plane before adding agent complexity.

BidPilot output: architecture map and service ownership map.

### 1. Transformer and LLM Foundations

Learn tokenization, embeddings, attention, self-attention, positional information, transformer blocks, inference, context windows, temperature, structured output, and tool calling.

BidPilot output: provider/model capability matrix and a small tokenizer/attention notebook or reproducible experiment.

### 2. Prompt and Context Engineering

Learn system instructions, few-shot examples, structured output, context packing, context compression, prompt injection, and instruction priority.

BidPilot output: versioned assistant and workflow prompt contracts.

### 3. RAG and Retrieval Engineering

Learn ingestion, parsing, chunking, metadata filters, sparse retrieval, dense retrieval, hybrid retrieval, RRF, query rewriting, reranking, context compression, and citation grounding.

BidPilot output: retrieval benchmark with Recall@K, MRR/nDCG, citation precision, and latency.

### 4. Agent Loops and Harnesses

Learn ReAct, tool calling, plan-and-execute, bounded loops, tool schemas, idempotency, retries, timeouts, cancellation, and typed results.

BidPilot output: one canonical assistant operator graph and one stable tool registry.

### 5. Workflow Orchestration

Learn routing, prompt chaining, parallelization, orchestrator-worker, evaluator-optimizer, supervisor, handoff, checkpointing, durable execution, and resume semantics.

BidPilot output: durable bid workflow with a persisted run state and human approval checkpoint.

### 6. Memory and Knowledge

Learn working memory, short-term thread state, episodic memory, semantic memory, procedural memory, memory extraction, consolidation, salience, decay, provenance, scopes, and deletion.

BidPilot output: project Wiki, organization memory candidates, evidence graph, and memory audit screen.

### 7. Safety, Governance, and Security

Learn sandboxing, policy enforcement, least privilege, human-in-the-loop, prompt injection defense, tool approval, tenant isolation, secret handling, audit logs, and data retention.

BidPilot output: server-enforced approval policy and adversarial test set.

### 8. Observability, Evaluation, and Operations

Learn traces, spans, structured events, golden datasets, offline evaluation, online evaluation, regression gates, SLOs, cost accounting, rate limiting, fallbacks, and incident response.

BidPilot output: eval runner, trace viewer, cost dashboard, and release gate.

## BidPilot Product Boundary

BidPilot is not a generic agent playground. Its product boundary is:

> A traceable AI bid-execution workspace that converts tender materials and organizational knowledge into reviewable, evidence-backed bid deliverables.

The moat is therefore not the number of agents. It is the combination of:

- a bid-domain ontology
- requirement-to-evidence-to-deliverable traceability
- organization-specific playbooks and memory
- workflow reliability and human approval
- evaluation data from real bid tasks

## Teaching Contract

For every implementation task, the assistant should explain:

- the concept and its industry vocabulary
- why BidPilot needs it
- the selected architecture and alternatives
- the relevant code path
- how the change is tested and measured
- what can fail in production
- how to describe the work in an interview
