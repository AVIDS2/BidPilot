# Release Checklist

## Goal

Provide one repeatable gate before promoting DocPilot between environments.
Use `docs/ops/production-release-evidence-matrix.md` to retain the concrete
artifact for each production-promotion item.

## Local readiness checklist

- migrations apply cleanly
- web, API, worker, worker-beat, database, cache, and object storage boot successfully
- one sample project can be created
- one staged Assistant attachment can be approved into a project bundle and reaches the ingest queue
- one sample draft flow runs to completion

## Staging promotion checklist

- release rehearsal core gate passes and retains a redacted artifact
  (`python scripts/release_rehearsal.py --run --output-file output/release-evidence/source-rehearsal.json`)
- a policy-based Agent quality gate passes with captured BidBench,
  RetrievalBench, MemoryBench, and AssistantBench reports from reviewed
  regression or hidden fixtures; development fixtures are not release evidence
- release candidate images built
- migration plan reviewed
- smoke checks pass
- one end-to-end BidPilot scenario verified
- relevant acceptance scenarios reviewed against current phase
- traces and logs visible
- known issues reviewed

## Production promotion checklist

- `uv run python scripts/run_quality_gate.py --policy benchmarks/bidbench/release-quality-gate-v1.json --bidbench-report <report> --retrieval-report <report> --memory-report <report> --assistant-report <report> --mode release --expected-git-commit <release-commit>` passes and its output artifact is retained
- `python scripts/production_readiness.py --target production` passes with production secret injection
- PostgreSQL and MinIO credentials are injected from the server secret store; no repository default or placeholder is in use
- Redis requires an authenticated internal URL and passes its health check before API and Worker start
- production API startup must fail if the required Redis-backed authentication limiters cannot initialize; a simulated limiter outage must return `503`, not silently allow login, registration, password-reset, or verification-email requests
- production API startup must also require an explicit trusted-proxy CIDR and a Redis-backed global API limiter; verify that a forged forwarding header from an untrusted peer cannot change the client budget
- `DOCPILOT_OFFICIAL_MONTHLY_TOKEN_CEILING` is explicitly configured, reviewed
  against the active provider/model mix, and verified by an official-model and
  server-owned embedding preflight rejection above the limit; confirm that a
  provider response with usage settles one ledger record and an omitted usage
  remains reserved as uncertain
- `readiness`, `migrate`, and `checkpoints` one-shot services complete successfully during deployment
- VPS pilot web and API domains resolve over HTTPS
- an HTTPS API smoke artifact from `scripts/load_smoke.py --require-https --output-file <artifact>` is retained with the release record
- email links point at the deployed app domain
- starter workflow quota blocks the 4th official-provider draft run
- backup dry-run and staging restore drill confirmed per `docs/ops/backup-restore-drill.md`
- rollback path and release owner confirmed
- secrets and environment config reviewed
- when Mem0 is enabled, run the isolated smoke without exposing its key:
  `uv run --directory services/api python ../../scripts/mem0_smoke.py`; the
  result must show `capture_status=queued`, `search_visible=True`, and
  `cleanup_status=deleted`
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
