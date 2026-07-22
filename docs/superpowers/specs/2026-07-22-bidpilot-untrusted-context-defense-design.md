# BidPilot Untrusted Context Defense v1

## Status

- Date: 2026-07-22
- Status: implemented and locally regression-verified
- Depends on: Unified Runtime v1, governed retrieval, memory context packing,
  structured workflow adapters, and server-side capability policy

## Problem

BidPilot processes tender documents, extracted evidence, long-term memory,
attachment metadata, reviewer feedback, and conversation history. Any of these
may contain indirect prompt-injection text such as an instruction to ignore the
system, reveal a secret, or trigger a platform operation.

The existing Operator planner already labels conversation history and memory
as untrusted, but its memory body is interpolated into a system message. The
drafting, requirement extraction, quality review, and graph extraction paths
also concatenate project text into natural-language prompts. That makes the
trust boundary inconsistent and hard to red-team.

OWASP identifies indirect prompt injection from documents and external sources
as a material Agent risk. Its recommended controls include separating external
content from user prompts, explicit trust boundaries, least-privilege tools,
human approval for high-risk actions, and adversarial testing. See
[OWASP LLM01](https://genai.owasp.org/llmrisk/llm01-prompt-injection) and
[OWASP LLMSVS 5.10-5.13](https://owasp.org/www-project-llm-verification-standard/LLMSVS-v2.0-en.html).

## Decision

Introduce a shared, pure `Untrusted Context` contract in `packages/contracts`.
Every model call that consumes project-originated text will use it.

```text
trusted system instructions + capability/policy boundary
                    |
                    v
             model invocation
                    ^
                    |
     serialized UNTRUSTED_CONTEXT_JSON in user-data position
     (evidence, document text, memory, attachments, review feedback)
```

The contract has two parts:

1. A static system-level guard. It tells the model that values in
   `UNTRUSTED_CONTEXT_JSON` are data, never instructions, and cannot alter
   tools, policy, approvals, system rules, data access, or output schema.
2. A deterministic JSON packet builder. Callers provide bounded, controlled
   field names and values. The packet labels the trust boundary and includes
   bounded heuristic risk categories such as instruction override, role
   impersonation, credential exfiltration, or tool/command coercion.

The detector is only a signal to strengthen model handling and red-team tests.
It does not block a document, mutate platform state, suppress a requirement,
or constitute a security authorization decision.

## Scope

v1 applies the boundary to every current model call that consumes business
context:

- OpenAI-compatible and Anthropic section drafting: evidence and review
  feedback;
- requirement extraction and quality review through the structured model
  adapter;
- controlled memory-graph extraction: approved memory title/body and citation
  labels;
- LangGraph Operator planning: conversation history, prior public result,
  attachment metadata, pending input, and long-term memory.
- legacy streaming chat and conversation-title generation: project context,
  conversation history, and generated-title source messages.

The Operator's static system prompt must contain only trusted platform
instructions and registered capability metadata. Long-term memory moves to the
human/user-data message as a serialized packet.

## Security Invariants

1. Untrusted text never enters a system message, developer instruction, tool
   description, capability registry, approval policy, or server-side command
   arguments by string concatenation.
2. A model still cannot execute an action merely because a document asks it to:
   the Runtime registry validates the selected capability, authorization,
   argument schema, policy, approval, idempotency, and audit event on the
   server.
3. Model output is treated as untrusted. Structured schemas and existing
   capability/claim/evidence validators remain the enforcement point.
4. Risk signals and tests contain categories/counts only; no source body,
   prompt, provider response, secret, or hidden reasoning is added to events
   or broadly visible logs.
5. The guard is appended after bounded trusted instructions so a long scenario
   prompt cannot truncate it.

## Red-Team Cases

The regression corpus includes representative strings that ask the model to:

- ignore previous/system instructions;
- impersonate system or developer roles;
- reveal prompts, credentials, or internal data; and
- call tools, execute commands, or bypass approval.

Tests assert that those strings remain only in the human/user-data message,
that trusted system messages contain the static guard but not injected data,
and that normal structured output/policy behavior stays unchanged.

## Non-Goals

- no claim that prompt injection is fully solved by a prompt or heuristic;
- no LLM-based content moderation or automatic safety score;
- no automatic document quarantine or deletion based solely on a marker;
- no browser-visible prompt, raw attachment text, or model reasoning trace;
- no expansion of Agent tool authority; and
- no replacement for authorization, approval, output validation, rate limits,
  tenant isolation, or secret management.

## Acceptance Criteria

1. Shared packet serialization is deterministic, bounded by callers, and
   preserves untrusted text only in the user-data position.
2. Every in-scope model path has the same static guard after its trusted
   instructions.
3. Operator memory is absent from the system message and present only in the
   serialized user-data packet.
4. OpenAI-compatible and Anthropic payload tests prove identical boundary
   behavior.
5. Structured extraction/review and graph-extraction red-team tests preserve
   output validation and authorized-evidence constraints.
6. Existing isolated API and Worker regressions pass without a provider call.

## Local Verification

- shared contract regression: `4 passed`;
- targeted Worker boundary regression: `22 passed`;
- full Worker suite: `127 passed`;
- targeted Assistant/runtime UI regression: `29 passed`;
- full API suite on the isolated `_test` database: `665 passed`;
- production frontend build: passed.
- API and Worker Ruff checks plus touched Python compilation: passed;
- frontend TypeScript check: passed.

This is code-level verification. It does not replace adversarial production
traces, retained CI artifacts, or a reviewed real-provider red-team exercise.
