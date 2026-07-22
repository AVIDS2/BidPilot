# Provider Reliability and Safe Failure Recovery

Date: 2026-07-18

## Objective

Make a real model-provider failure visible, durable, retryable only when safe,
and recoverable by a product user. A provider outage must never create a
synthetic successful draft or disclose credentials, raw provider diagnostics,
or prompts.

## Implemented

- Added `ProviderInvocationError` as the Worker adapter failure contract.
  It carries a stable error code, a public-safe message, and retryability.
- OpenAI-compatible and Anthropic adapters now raise typed failures for
  authentication, model/endpoint, invalid request, rate limit, timeout,
  unavailability, and invalid responses. The deterministic stub remains
  explicit local/test behavior only.
- A missing/deleted BYOK record now terminates as `provider_config_missing`;
  it cannot fall through to the platform provider key.
- The LangGraph section-drafter resolves the provider inside the typed failure
  boundary, retries only transient typed failures up to three times, and routes
  every terminal failure to `END` before review or persistence.
- Public runtime events carry stable error codes but no raw exception text.
  The API drafting SSE stream now emits `provider_retry` and error-code-bearing
  terminal events.
- The React Assistant renders retry attempt progress and localized recovery
  guidance. Configuration, authentication, model, and request failures expose
  an explicit path to model-service settings.
- Worker tests now refuse to run unless `DOCPILOT_TEST_DATABASE_URL` (or an
  already-test-suffixed application URL) points at a database ending in `_test`.
  This aligns the Worker with API test isolation.
- The standalone Worker GitHub Actions job now provisions PostgreSQL and Redis,
  installs API migration dependencies, and applies Alembic migrations before
  tests. Without this, the new test guard would correctly fail CI.

## Verification

- Migrated isolated local database: `docpilot_test`.
- Worker targeted tests: `9 passed`.
- API drafting streaming tests: `2 passed`.
- Worker full suite: `88 passed`.
- API full suite: `569 passed`.
- Web full suite: `25 files / 91 tests passed`.
- Web TypeScript check and production Vite build passed.
- Worker/API Ruff checks passed for touched files.

## Review Notes

- Local contract review confirmed that failed graph state routes to `END` and
  cannot reach `persist_result`.
- A requested Claude Code read-only review was started with no edit permissions
  but timed out without findings. It is not considered review evidence.
- This verifies deterministic failure behavior only. Real provider credentials,
  vendor failure responses, production runtime events, and VPS streaming still
  require controlled deployment evidence before pilot promotion.

## Follow-up

1. Add controlled provider contract probes for configured production providers
   without sending user data.
2. Capture a deployed workflow failure/retry trace as release evidence.
3. Define any future cross-provider failover as a separately approved policy
   with model compatibility, cost reservation, user consent, and audit UX.
