# 2026-07-18 Trusted Proxy and Global API Rate Limiting

## Decision

The public API resolves a caller address from `X-Forwarded-For` or `X-Real-IP`
only when the direct socket peer belongs to the explicit
`DOCPILOT_TRUSTED_PROXY_CIDRS` allowlist. All other callers are keyed by their
direct peer address. This keeps an arbitrary request header from changing its
rate-limit identity or the optional Turnstile `remoteip` value.

The global per-client API budget is a fixed-window Redis counter. Production
uses `DOCPILOT_REDIS_URL` unless an authenticated
`DOCPILOT_RATE_LIMIT_STORAGE_URI` is deliberately provided. It fails closed
when Redis is unavailable; local development may use the existing in-memory
fallback.

Registration and password-reset requests now have separate lower Redis-backed
budgets keyed by the same client identity fingerprint. They are checked before
the Turnstile verification or email delivery work, and fail closed on a Redis
outage in production.

## Why

The prior application-wide limiter was process-local and hard-coded, so it did
not provide one shared budget across API replicas. The prior Turnstile helper
also accepted forwarding headers regardless of the direct peer. Both behaviors
are inappropriate for a public reverse-proxied deployment.

## Operational Requirement

The deployment owner must identify the actual OpenResty-to-container peer CIDR
and configure `DOCPILOT_TRUSTED_PROXY_CIDRS` on the VPS. OpenResty must replace
rather than append forwarded client headers. This is deliberately a deployment
evidence item, not a value guessed or committed by source code.

## Health Signal

`GET /health` is now liveness-only and bypasses the global API limiter. `GET
/health/ready` checks PostgreSQL, Redis, and object storage with safe status
labels. The production API container uses the readiness endpoint as its Docker
health check; detailed admin health no longer returns raw dependency errors.
