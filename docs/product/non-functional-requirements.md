# Non-Functional Requirements

## Goal

Define the production-grade expectations for `DocPilot` beyond feature completeness.

This document exists so future implementation can optimize for real operation, not just demo success.

## Scope

These requirements apply to the `DocPilot` core and the first scenario package, `BidPilot`.

## Service quality targets

### Availability

- staging should support repeatable validation with no manual one-off fixes
- production API availability target: `99.5%`
- production worker completion target for non-provider failures: `99.0%`

### Performance

Target starting point for standard bundles:

- project creation request: p95 under `500 ms`
- bundle registration request: p95 under `1 s`
- parse completion: `95%` within `15 minutes`
- section drafting completion: `95%` within `5 minutes`
- review action write path: p95 under `1 s`
- approved export generation: `95%` within `10 minutes`

### Durability

- business truth must survive worker restarts and provider failures
- generated section history must be immutable and queryable
- audit events must be append-only
- raw source files and exported artifacts must be recoverable from object storage and metadata records

## Recovery targets

### Initial targets

- database backup frequency: daily logical backup minimum
- object storage versioning: enabled in staging and production where supported
- recovery point objective (`RPO`): `24 hours` maximum in the initial production phase
- recovery time objective (`RTO`): `4 hours` maximum in the initial production phase

### Later targets

After the product has real external usage, tighten to:

- `RPO`: `4 hours`
- `RTO`: `1 hour`

## Data and governance requirements

- every generated section must have at least one evidence record or an explicit missing-evidence marker
- every write action must carry actor attribution
- every execution run must retain provider, parser, adapter, and prompt version metadata
- every export must be traceable to approved section versions
- project-scoped access must apply consistently across source files, generated outputs, and review artifacts

## Scalability assumptions

Initial production assumptions:

- single region deployment
- one primary relational database
- one queue backend
- one object storage backend
- low to moderate concurrent editing volume

The system must scale vertically first, then split by service only when measurable pressure justifies it.

## Operational requirements

- all services emit structured logs
- traces must correlate request, run, job, and provider activity
- dashboards must expose queue depth, job latency, parse success, draft success, export success, and cost usage
- alerts must exist for queue saturation, export failure, high parse failure rate, and critical auth issues

## Security requirements

- no production secrets in repository or frontend payloads
- RBAC enforcement before production launch
- export access must be policy-checked
- security-significant actions must enter the audit stream
- destructive maintenance actions must require explicit operator confirmation

## Delivery quality bar

No phase is considered complete for promotion unless:

- acceptance scenarios for that phase pass
- required tests and smoke checks pass
- docs remain aligned with implementation
- rollback or recovery path is documented where relevant

## Change control

Any change that materially affects latency, recovery targets, security posture, or deployment shape must update this document and the relevant runbook or ADR.
