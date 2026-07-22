# Untrusted Context Defense v1

## Problem

Tender documents, extracted evidence, attachment metadata, reviewer feedback,
conversation history, and approved long-term memory are all externally or
business-originated content. They can contain indirect prompt-injection text.
Several model paths previously embedded that content inside natural-language
system prompts, making the trust boundary inconsistent.

## Decision

Introduce a shared `packages/contracts/untrusted_context.py` contract.

- Trusted instructions stay in static system prompts.
- Caller-controlled fields are serialized into deterministic
  `UNTRUSTED_CONTEXT_JSON` packets in the user-data position.
- The static guard tells the model that packet values are data, never policy,
  tool authority, approval, access control, or system instructions.
- Heuristic markers are observable signals only. They never authorize,
  quarantine, mutate, or suppress data by themselves.

The server-side Runtime registry, authorization, typed schemas, policy,
approval, idempotency, audit, and output validation remain the actual
enforcement boundary.

## Applied Paths

- OpenAI-compatible and Anthropic drafting adapters;
- structured requirement extraction and quality review;
- approved memory-graph extraction;
- production LangGraph Operator planning, including memory and history;
- legacy streaming chat and title generation.

## Related Boundary Fix

An explicit BYOK provider configuration is now fail-closed in the Assistant
router. A missing, inactive, deleted, or unauthorized selected configuration
returns a safe error. Only an absent selection may use the official
platform-funded provider. The browser clears a stale selection but does not
silently resend the user's request with the platform model.

## Verification

- shared contract tests: `4 passed`;
- targeted Worker boundary tests: `22 passed`;
- full Worker suite: `127 passed`;
- Assistant/runtime UI tests: `29 passed`;
- full API suite on `docpilot_claim_integrity_test`: `665 passed`;
- production frontend build: passed.
- API and Worker Ruff checks, touched Python compilation, and frontend
  TypeScript check: passed.

## Residual Risk

Prompt injection cannot be eliminated by a system prompt or a text detector.
The next release evidence should include controlled real-provider adversarial
traces, retained CI artifacts, and review of high-risk `full_access` policy
assignments. No raw document text, provider diagnostic, secret, or hidden
reasoning should be exposed in those artifacts.
