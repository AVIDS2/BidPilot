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
2. API tests
3. frontend typecheck
4. frontend unit tests
5. frontend build

## Execute the core rehearsal

```powershell
python scripts/release_rehearsal.py --run
```

## Optional browser smoke

Use this when the web flow changed or before a release candidate:

```powershell
python scripts/release_rehearsal.py --run --include-browser
```

This runs the unauthenticated Playwright browser smoke tests. The seeded demo flow remains opt-in through `E2E_DEMO=1` because it requires local API services and seeded data.

## Optional load smoke

Start the API first, then run:

```powershell
python scripts/release_rehearsal.py --run --include-load
```

The load smoke calls `/health` and `/openapi.json` through `scripts/load_smoke.py`.

## Optional production readiness

Inject production-shaped secrets first, then run:

```powershell
python scripts/release_rehearsal.py --run --include-production-readiness
```

This calls `scripts/production_readiness.py --target production` and should fail if required secrets are missing, localhost endpoints are used, or development defaults are present.

## Commercialization readiness note

This rehearsal supports MVP-to-pilot readiness. Commercial launch still needs customer onboarding, billing/contract terms, support ownership, pricing, telemetry review, backup/restore sign-off, and a named release owner.
