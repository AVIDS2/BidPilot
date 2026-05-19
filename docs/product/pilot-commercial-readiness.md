# Pilot Commercial Readiness

This document defines the commercial framework for the DocPilot controlled pilot.
Items requiring a named decision from the pilot owner are marked **[OWNER]**.

## Pilot owner and customer contact

| Role | Name | Contact |
|------|------|---------|
| Pilot owner (DocPilot side) | **[OWNER]** | — |
| Customer primary contact | **[OWNER]** | — |
| Technical escalation | Bootstrap admin (`2141325767@qq.com`) | — |

The pilot owner is responsible for: approving pilot start, accepting success criteria, and authorizing pilot exit or extension.

## Pilot duration and success criteria

### Recommended duration

- **Pilot window**: 4 weeks from first user onboarding
- **Extension**: +2 weeks if success criteria are partially met and no P0/P1 issues are open

### Success criteria

| # | Criterion | Measurement |
|---|-----------|-------------|
| 1 | At least one BidPilot project completes source upload → DOCX export | E2E Playwright + manual verification |
| 2 | Generated sections include evidence links or missing-evidence markers | Automated check in review tab |
| 3 | Customer primary contact confirms output quality is acceptable for their use case | Written sign-off |
| 4 | No P0/P1 operational risks remain open | Issue tracker review |
| 5 | Backup and restore process is verified | Restore drill completed |
| 6 | API availability ≥ 99.5% during pilot window | SLO monitoring |

**[OWNER]** must agree to these criteria before pilot start.

## Data handling expectations

### Data classification

| Category | Examples | Retention | Access control |
|----------|----------|-----------|----------------|
| **Customer content** | Uploaded RFPs, generated drafts, export artifacts | Until project deletion + 30-day grace | Project members only |
| **System metadata** | Audit events, execution runs, user accounts | 90 days rolling (audit) / indefinite (accounts) | Admin-only for governance data |
| **Operational telemetry** | Health checks, latency metrics, error rates | 30 days rolling | Admin + monitoring system |
| **Authentication data** | Password hashes, email verification tokens | Until account deletion | Never exposed outside auth module |

### Data residency

- All data resides in the PostgreSQL instance and MinIO/S3 bucket configured for the deployment
- No data is transmitted to third-party AI providers beyond the prompt/response pairs defined by the adapter contract
- AI provider API calls use TLS 1.2+; response payloads are not stored by the provider (per provider DPA)

### Data isolation

- Single-tenant model: all customer content shares the same database and storage
- Project-level isolation: users can only access projects they are members of
- Admin users can view audit and system metadata across all projects

### Data deletion

- Project deletion removes all associated bundles, documents, sections, requirements, deliverables, and export artifacts
- MinIO buckets are deleted on project deletion
- Audit events are retained for 90 days regardless of project deletion
- User account deletion removes personal data; anonymized audit references remain

### Backup and recovery

- Daily backup via `scripts/backup.py` (pg_dump)
- Restore drill validated per `docs/ops/backup-restore-drill.md`
- RPO target: 24 hours; RTO target: 2 hours

## Support response expectations

### Support tiers

| Severity | Definition | Target response | Target resolution |
|----------|-----------|-----------------|-------------------|
| **P0 — Critical** | System down, data loss, security breach | 1 hour | 4 hours |
| **P1 — High** | Core workflow blocked, no workaround | 4 hours | 24 hours |
| **P2 — Medium** | Feature impaired, workaround available | 1 business day | 3 business days |
| **P3 — Low** | Cosmetic, enhancement request | 3 business days | Next release |

### Support channels

- **Primary**: Email to bootstrap admin (`2141325767@qq.com`)
- **Escalation**: Pilot owner (**[OWNER]**)
- **Self-service**: `docs/ops/` runbooks and `docs/product/known-limitations.md`

### Monitoring and alerting

- Health endpoint: `GET /health` (liveness) and `GET /ops/health-detailed` (readiness)
- SLO targets defined in `docs/ops/slo-error-budgets.md`
- Error budget burn rate alerting: fast burn (14.4x) and slow burn (6x)

### On-call expectations during pilot

- Business hours (09:00–18:00 UTC+8): P0/P1 response within target
- After hours: P0 response within 2 hours; P1 next business day
- **[OWNER]** to confirm on-call coverage arrangement

## Pricing

### Pilot pricing model

Pricing remains **exploratory** during the controlled pilot. No commercial agreement is required to start the pilot.

The pilot uses the existing subscription model:

| Plan | Projects | Price during pilot |
|------|----------|-------------------|
| Starter | 3 | Free |
| Professional | Unlimited | Free (pilot evaluation) |
| Enterprise | Unlimited + SLA | Free (pilot evaluation) |

### Post-pilot pricing

Pricing will be defined before pilot exit based on:

1. Actual usage patterns observed during the pilot
2. Customer willingness-to-pay signals
3. Competitive positioning analysis
4. Cost-of-delivery calculation (infrastructure + AI provider costs)

**No pricing commitment is implied by pilot participation.**

A signed commercial agreement is required before any billing activation.

### Pricing remains exploratory unless

- A signed commercial agreement exists, OR
- The pilot owner explicitly transitions from pilot to commercial mode

## Document review

This document should be reviewed and updated:

- Before pilot start (fill in **[OWNER]** fields)
- At pilot midpoint (verify criteria progress)
- At pilot exit (record outcomes and pricing decisions)
