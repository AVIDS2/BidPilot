# DocPilot SLO and Error Budget Definitions

## Service Level Indicators (SLIs)

| SLI | Description | Measurement |
|-----|-------------|-------------|
| **API Availability** | Percentage of successful HTTP responses | `2xx responses / total responses` |
| **Draft Latency** | Time from draft request to version stored | P95 of `run.completed_at - run.started_at` |
| **Ingest Latency** | Time from bundle registration to ingest complete | P95 of `bundle.ingested_at - bundle.created_at` |
| **Export Latency** | Time from export request to DOCX served | P95 of response time for `/export/.../docx` |

## Service Level Objectives (SLOs)

| SLO | Target | Window |
|-----|--------|--------|
| API Availability | ≥ 99.5% | 30-day rolling |
| Draft Latency P95 | ≤ 30s (with LLM), ≤ 5s (stub) | 7-day rolling |
| Ingest Latency P95 | ≤ 60s per document | 7-day rolling |
| Export Latency P95 | ≤ 10s | 7-day rolling |

## Error Budgets

Based on 99.5% availability SLO over 30 days:

- **Budget**: 0.5% downtime = ~3.6 hours/month
- **Burn rate alerting**: 
  - Fast burn: 14.4x rate → alert if >2% of requests fail in 1 hour
  - Slow burn: 6x rate → alert if >1% of requests fail in 6 hours

## Incident Response

1. **Detect**: Health check (`/ops/health-detailed`) returns `degraded`
2. **Triage**: Check which dependency is failing (Postgres/Redis/MinIO)
3. **Mitigate**: 
   - Postgres down → check connection pool, restart
   - Redis down → Celery tasks queue locally, restart Redis
   - MinIO down → uploads/exports fail gracefully, serve cached DOCX
4. **Recover**: Use `POST /execution/runs/{id}/retry` for failed runs
5. **Post-mortem**: Record in audit trail, update runbooks

## Monitoring Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /health` | Liveness probe (always returns ok if process alive) |
| `GET /ops/health-detailed` | Readiness probe (checks Postgres, Redis, MinIO) |
| `GET /ops/runtime-summary` | Queue depth, failed runs, success rate |
| `GET /ops/runtime-runs/{run_id}/diagnostics` | Administrator-only redacted run correlation: state, retries, approval wait, token counters, retrieval metrics, audit and deliverable links |

## Local load smoke

Use `scripts/load_smoke.py` for a lightweight local API pressure check before release candidates or ops changes.

```powershell
python scripts/load_smoke.py --base-url http://localhost:8000 --requests 20 --concurrency 4 --max-error-rate 0 --max-p95-ms 1000
```

The default endpoints are `/health` and `/openapi.json`. Add additional `--endpoint` values for targeted readiness or export checks. For a deployed target, add `--require-https --output-file output/release-evidence/api-load-smoke.json` so the result can be retained without recording credentials.
