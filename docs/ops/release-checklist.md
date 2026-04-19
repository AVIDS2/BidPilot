# Release Checklist

## Goal

Provide one repeatable gate before promoting DocPilot between environments.

## Local readiness checklist

- migrations apply cleanly
- web, API, worker, database, cache, and object storage boot successfully
- one sample project can be created
- one sample draft flow runs to completion

## Staging promotion checklist

- release candidate images built
- migration plan reviewed
- smoke checks pass
- one end-to-end BidPilot scenario verified
- relevant acceptance scenarios reviewed against current phase
- traces and logs visible
- known issues reviewed

## Production promotion checklist

- backup confirmed
- rollback path confirmed
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
