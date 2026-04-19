# Configuration and Secrets

## Goal

Provide one stable place for environment variables, secret ownership, and configuration discipline.

This document prevents future implementation from inventing config ad hoc.

## Configuration principles

- every new environment variable must have a documented owner and purpose
- secrets and non-secret config should be distinguishable
- local development must work with safe defaults where possible
- production secrets must never be committed to the repository

## Service configuration groups

### Web

Typical categories:

- API base URL
- auth and session configuration
- feature flags for non-production features
- telemetry browser settings

### API

Typical categories:

- database connection
- cache or queue connection
- object storage connection
- auth settings
- provider keys and endpoints
- telemetry export settings

### Worker

Typical categories:

- queue backend
- database connection
- object storage connection
- provider and parser adapter settings
- concurrency and retry tuning
- telemetry export settings

## Baseline variables

These names are the preferred starting point for implementation.

### Shared

- `DOCPILOT_ENV`
- `DOCPILOT_LOG_LEVEL`
- `DOCPILOT_APP_URL`

### API and worker

- `DOCPILOT_DATABASE_URL`
- `DOCPILOT_REDIS_URL`
- `DOCPILOT_S3_ENDPOINT`
- `DOCPILOT_S3_BUCKET`
- `DOCPILOT_S3_ACCESS_KEY`
- `DOCPILOT_S3_SECRET_KEY`

### AI adapters

- `DOCPILOT_PROVIDER_OPENAI_BASE_URL`
- `DOCPILOT_PROVIDER_OPENAI_API_KEY`
- `DOCPILOT_PROVIDER_DOMESTIC_BASE_URL`
- `DOCPILOT_PROVIDER_DOMESTIC_API_KEY`

### Telemetry

- `DOCPILOT_OTEL_EXPORTER_ENDPOINT`
- `DOCPILOT_LANGFUSE_PUBLIC_KEY`
- `DOCPILOT_LANGFUSE_SECRET_KEY`
- `DOCPILOT_LANGFUSE_HOST`

### Security

- `DOCPILOT_AUTH_MODE`
- `DOCPILOT_JWT_SECRET`
- `DOCPILOT_SESSION_SECRET`

## Environment strategy

### Local

- prefer `.env.local` or service-specific local env files ignored by git
- safe dummy or development credentials are acceptable
- local config should default toward developer productivity

### Staging

- all secrets come from a managed source or deployment secret injection
- staging should mirror production contract shape even if scale differs

### Production

- all secrets come from a managed secret source
- rotation procedure must exist for provider keys, JWT secrets, and storage credentials
- secret values must not appear in logs, traces, or event payloads

## Ownership and update rule

Every added variable should answer:

- which service uses it
- whether it is secret
- what default, if any, is allowed locally
- what breaks if it is missing or invalid

If a new subsystem introduces configuration, update this document in the same change.
