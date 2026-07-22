# Platform Model Cost Ceiling

## Decision

Platform-funded LLM usage is no longer allowed to rely only on plan-level
request counts or an optional organization setting. Staging and production now
require `DOCPILOT_OFFICIAL_MONTHLY_TOKEN_CEILING`, a non-secret per-workspace
maximum. The effective official limit is the minimum of that ceiling and an
optional lower organization safeguard. BYOK continues to use a separate ledger
and does not consume platform-funded capacity.

## Enforcement path

1. API workflow and Operator planning reserve tokens before provider dispatch.
2. The shared ledger locks the organization row before calculating recorded
   and active-reservation totals, including the first request where no optional
   budget row exists yet.
3. Worker-owned physical workflow calls re-check hosted configuration and
   refuse an official call that lacks a committed preflight reservation.
4. Production readiness rejects a missing, negative, or malformed ceiling.

## Deliberate boundary

This protects LLM calls with provider-reported token accounting. It is not a
currency spend ledger and does not yet meter embedding provider tokens.
Document indexing remains bounded by its existing server-side indexing-job
quota until embedding usage can be recorded from provider responses.

## Evidence

- API usage/readiness regression: `19 passed`.
- API workflow, Operator, and quota regression: `46 passed`.
- Worker model-reservation and governed-node regression: `21 passed`.
- Targeted API and Worker Ruff checks passed.
