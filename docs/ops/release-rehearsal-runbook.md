# Release Rehearsal Runbook

## Goal

Run one repeatable release-candidate rehearsal before promoting DocPilot to staging or production.

## Default dry run

Print the release gate sequence without executing commands:

```powershell
python scripts/release_rehearsal.py
```

The default sequence checks:

1. API migrations
2. API static checks
3. API tests
4. Worker static checks
5. Worker tests
6. frontend typecheck
7. frontend unit tests
8. frontend build

## Execute the core rehearsal

The rehearsal runs migrations and tests only against the dedicated test
database. Set `DOCPILOT_TEST_DATABASE_URL` to a connection whose database name
ends in `_test`; otherwise the command refuses to start. On the documented
local Docker baseline, create it once with:

```powershell
uv run --directory services/api python ../../scripts/prepare_local_test_database.py
```

```powershell
python scripts/release_rehearsal.py --run
```

To retain a redacted source-release record alongside the local or CI release
evidence, add an output path under the ignored `output/` directory:

```powershell
python scripts/release_rehearsal.py --run `
  --output-file output/release-evidence/source-rehearsal.json
```

The JSON artifact records only the Git commit, tracked-worktree state, step
names, return codes, durations, and final result. It never records environment
variables, database URLs, command output, provider diagnostics, or source
documents. `--output-file` requires `--run` and writes an artifact even when a
gate fails.

## Optional browser smoke

Use this when the web flow changed or before a release candidate:

```powershell
python scripts/release_rehearsal.py --run --include-browser
```

This runs the unauthenticated Playwright browser smoke tests. The seeded demo flow remains opt-in through `E2E_DEMO=1` because it requires local API services and seeded data.

Playwright starts an isolated Vite server on `127.0.0.1:5174` by default. It
does not reuse an already-running developer server unless
`E2E_REUSE_SERVER=1` is set deliberately. Use `E2E_BASE_URL` only when the
target deployment itself is the intended browser-test subject.

For an authenticated local run, set `E2E_API_URL` to the explicit API process
that was started against the dedicated `_test` database. The Vite server and
the Playwright admin-verification requests then use that same URL. Never point
`E2E_DEMO=1` at an unknown process on port `8000` or a development/production
database.

## Optional load smoke

Start the API first, then run:

```powershell
python scripts/release_rehearsal.py --run --include-load
```

The local load smoke calls `/health` and `/openapi.json` through `scripts/load_smoke.py`.
For a deployed API, require HTTPS and retain a redacted evidence artifact with
the release record:

```powershell
python scripts/load_smoke.py `
  --base-url https://bidpilot-api.rglens.com `
  --endpoint /health `
  --endpoint /health/ready `
  --require-https `
  --requests 20 `
  --concurrency 4 `
  --max-error-rate 0 `
  --max-p95-ms 1000 `
  --output-file output/release-evidence/api-load-smoke.json
```

The command refuses credential-bearing URLs and records only endpoint names,
status codes, latency, thresholds, and the pass/fail result.

## Optional production readiness

Inject production-shaped secrets first, then run:

```powershell
python scripts/release_rehearsal.py --run --include-production-readiness
```

This calls `scripts/production_readiness.py --target production` and should fail if required secrets are missing, localhost endpoints are used, or development defaults are present.

## Required Agent quality gate for promotion

Before staging or production promotion, capture one reviewed BidBench,
RetrievalBench, MemoryBench, and AssistantBench report from the release commit. Use only
`regression` or `hidden` fixtures for this step; the visible development
fixtures are useful for engineering but cannot make a release eligible. Each
captured input must carry the same redacted `evidence_set_id` and `capture_id`, an allowed
capture kind (`current_pipeline` or `reviewed_snapshot`),
`two_person_review`, a non-empty attestation reference, and a timestamp no
older than the policy limit (seven days by default). Keep the referenced CI
artifact and review record outside the repository.

Run the gate directly:

```powershell
uv run python scripts/run_quality_gate.py `
  --policy benchmarks/bidbench/release-quality-gate-v1.json `
  --bidbench-report <bidbench-report.json> `
  --retrieval-report <retrieval-report.json> `
  --memory-report <memory-report.json> `
  --assistant-report <assistant-report.json> `
  --mode release `
  --expected-git-commit <release-commit>
```

Or include the exact same gate in the rehearsal sequence:

```powershell
python scripts/release_rehearsal.py --run `
  --include-quality-gate `
  --quality-gate-policy benchmarks/bidbench/release-quality-gate-v1.json `
  --bidbench-report <bidbench-report.json> `
  --retrieval-report <retrieval-report.json> `
  --memory-report <memory-report.json> `
  --assistant-report <assistant-report.json> `
  --quality-gate-git-commit <release-commit>
```

The command writes an audit artifact under `output/quality-gate/`. Retain it
with the release record. It contains report hashes, redacted provenance, and
metric outcomes, not customer documents, prompts, provider payloads, or
secrets. The gate verifies policy completeness, not a CI platform signature;
the attestation reference must remain resolvable in the release system.

## Commercialization readiness note

This rehearsal supports MVP-to-pilot readiness. Commercial launch still needs customer onboarding, billing/contract terms, support ownership, pricing, telemetry review, backup/restore sign-off, and a named release owner.
