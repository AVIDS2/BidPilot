# Production Authentication Rate-Limit Hardening

- Date: 2026-07-18
- Scope: prevent Redis rate-limiter failure from becoming an authentication abuse bypass
- Status: implementation and focused verification complete

## Problem

The API already supported Redis-backed rate limits, but a startup connection
failure could silently fall back to in-memory counters and a runtime Redis
failure could allow the request. That behavior is acceptable only for local
development; it is not a safe public authentication boundary.

## Decision

Production requires Redis-backed login and verification-resend rate limits.
Missing or unreachable Redis fails API initialization, while a runtime limiter
failure returns a generic `503` before credential checking or email sending.
Development remains allowed to use an in-memory limiter.

The Redis increment and expiry are now one Lua operation, avoiding a permanent
counter if a process exits between separate `INCR` and `EXPIRE` commands.
Failure logs never include the Redis URL, key, or user identifier.

## Verification

```powershell
uv run --directory services/api pytest tests/security/test_redis_rate_limiter.py tests/auth/test_rate_limiter_availability.py tests/auth/test_email_verification.py -q
# 17 passed

python -u scripts/release_rehearsal.py --run
# API migrations passed
# API static checks passed
# API 487 passed
# Worker static checks passed
# Worker 78 passed
# frontend typecheck passed
# Web 25 files / 89 tests passed
# production build passed
```

## Remaining Scope

This hardens the existing email-keyed login and resend paths. Registration,
password-reset, and trusted-proxy client-IP budgets are separate public-launch
work so that proxy trust and user-facing retry semantics can be designed
deliberately.
