# Governed Memory Release-Gate Log

- Date: 2026-07-17
- Scope: governed memory/Bid Wiki release evidence, citation integrity, and production configuration hardening
- Status: implementation and local verification complete; production rollout remains intentionally blocked on independent review and a credential-rotation window

## Delivered

1. Memory is a PostgreSQL ledger with append-only memory events, project/user scopes, approval-gated shared records, source-backed compiler proposals, and profile-aware retrieval.
2. MemoryBench evaluates redacted context observations only. Its reports carry fixture fingerprints, policy version, retrieval profile, recall, isolation, provenance, ownership, budget, and degraded-mode metrics without copying memory bodies into benchmark artifacts.
3. The API now resolves every client-supplied citation against the current caller's authorized project before persistence. It rejects nonexistent or cross-project identifiers and derives the user-facing source label and locator on the server.
4. Project-scoped personal memory is only readable through an authorized project request. An unscoped personal-memory list contains global personal memory only.
5. Production Compose/readiness configuration no longer permits repository-default PostgreSQL, MinIO, or Redis credentials. Redis requires authentication, SMTP requires a usable From identity and password, and the deployed Assistant/checkpointer configuration must be production-safe.

## Verification Evidence

```powershell
$env:DOCPILOT_DATABASE_URL='postgresql+psycopg://docpilot:docpilot@localhost:5433/docpilot_migration_test'
uv run --directory services/api pytest -q
# 456 passed

uv run --directory services/worker pytest -q
# 78 passed

pnpm --filter @docpilot/web test -- --run
# 25 files, 88 tests passed

pnpm --filter @docpilot/web build
# passed; public pages and the authenticated workspace shell are split, and the build reports no large-chunk warning

node --input-type=module -
# SHIKI_FINE_GRAINED_SMOKE_OK (browser-compatible JavaScript engine, selected languages/themes only)

pnpm --filter @docpilot/web exec playwright test e2e/auth.spec.ts e2e/pricing.spec.ts --grep-invert '@api' --workers=2
# 16 passed (desktop Chromium and Pixel 7 public auth and pricing routes)

git diff --check
# no whitespace errors; Windows line-ending warnings only
```

## Release Blockers And Follow-up

1. The existing VPS is healthy but still runs the older commit. Do not deploy this change until the PostgreSQL, MinIO, and Redis credentials are rotated through their respective administrative paths and the production `.env` passes the new readiness gate.
2. Two read-only Claude CLI review attempts, including a targeted review of the new lazy workspace shell and browser highlighter, timed out without a verdict. They are not independent-review evidence; a human or successful external code review is still required before production deployment.
3. Desktop Chromium and Pixel 7 validation now cover public auth and pricing routes. Authenticated backend flows and visual assertions beyond semantic browser checks remain release requirements; the embedded Codex browser is intentionally not used because it is known to crash in this environment.
4. Existing production memory records predating server-side citation validation should be audited or recompiled before claiming full provenance coverage.
