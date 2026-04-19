# Environment Matrix

## Goal

Define what each environment is for and what is expected to differ or stay the same.

## Environments

### Local

Purpose:

- daily development
- debugging
- smoke validation

Requirements:

- single-machine friendly
- no cloud-only dependency required
- safe local secrets and fixtures

Expected services:

- web
- api
- worker
- postgres
- redis
- minio

### Staging

Purpose:

- integration validation
- release rehearsal
- backup and restore drills

Requirements:

- environment parity with production contracts
- seeded acceptance scenario data
- observability enabled

### Production

Purpose:

- durable external-facing operation

Requirements:

- hardened secrets management
- backup and restore discipline
- alerting and SLO review
- auditable deployment and rollback path

## What should stay consistent

- API contracts
- event contracts
- environment variable names
- auth boundary shape
- object storage contract
- queue and run-state semantics

## What may differ

- scale and resource sizing
- provider quotas or provider routing
- storage class or managed service provider
- non-production feature flags

## Promotion rule

A deployment should move forward only when the release checklist and acceptance scenarios for that phase are satisfied in the current target environment.
