# Release Checklist

## Goal

Provide one repeatable gate before promoting DocPilot between environments.

## Local readiness checklist

- migrations apply cleanly
- web, API, worker, database, cache, and object storage boot successfully
- one sample project can be created
- one sample draft flow runs to completion

## Staging promotion checklist

- release rehearsal core gate passes (`python scripts/release_rehearsal.py --run`)
- release candidate images built
- migration plan reviewed
- smoke checks pass
- one end-to-end BidPilot scenario verified
- relevant acceptance scenarios reviewed against current phase
- traces and logs visible
- known issues reviewed

## Production promotion checklist

- `python scripts/production_readiness.py --target production` passes with production secret injection
- backup dry-run and staging restore drill confirmed per `docs/ops/backup-restore-drill.md`
- rollback path and release owner confirmed
- secrets and environment config reviewed
- SLO and alert coverage checked
- error budget is not already exhausted
- deployment owner identified
- production-facing expectations in `docs/product/non-functional-requirements.md` reviewed

## Post-release checklist

- verify health endpoints
- verify queue depth is normal
- verify one draft and one export path
- review traces for abnormal latency
- record release summary and follow-up issues
