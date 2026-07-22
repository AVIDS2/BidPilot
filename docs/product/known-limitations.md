# Known Limitations (Pre-Pilot)

This document lists known limitations that must be acknowledged before onboarding pilot users.

## Authentication & Access

- Email verification is enforced at login; unverified users cannot authenticate. Admin can manually verify via `POST /auth/users/{id}/verify`.
- Verification and password-reset delivery depend on the deployment SMTP configuration. A personal mailbox SMTP connection is suitable for a pilot, but it does not provide a production sending domain, SPF/DKIM/DMARC alignment, or sender reputation.
- Server-side refresh token storage with per-token revocation.
- Production login and verification-email resend limits, plus the global
  client-IP API budget, require Redis and fail closed if the limiter cannot
  initialize or check a request. Forwarded client headers are accepted only
  from configured trusted proxies. Development may use an in-memory fallback.
  IP reputation, WAF policy, account-takeover telemetry, and distributed abuse
  detection still need broader public-launch controls.

## AI & Generation

- AI generation requires configured server-side provider keys for real output. Provider credentials are never supplied by the browser; unavailable providers must surface a governed failure rather than a fabricated success.
- BidBench, RetrievalBench, MemoryBench, AssistantBench, and a policy-based
  four-report quality gate exist, but the repository contains only synthetic
  development fixtures. Frozen regression/hidden fixtures, captured production
  traces, and a reviewed release-quality report are still required before
  quality claims.
- No automatic red-team or compliance scoring.
- Official-provider use is recorded in a durable monthly usage ledger. The current starter policy enforces 3 workflow runs, 100 Assistant messages, and 5 indexing starts per month; BYOK is not charged to the platform quota. Feature and seat entitlements remain incomplete.

## Review & Collaboration

- No real-time collaborative editing; users must refresh to see changes from others.
- Review threads are per-section only; no cross-section or document-level review threads.
- Review notification emails are sent on approve/reject decisions.

## Data & Export

- Data export includes all entity types (projects, bundles, documents, deliverables, sections, requirements, evidence, execution_runs, review_comments).
- DOCX export includes only approved sections; rejected or draft sections are excluded.
- PDF export available alongside DOCX.

## Operations

- No validated horizontal-scaling strategy; the initial deployment uses one API process plus separate Worker and Worker Beat services.
- Production deployment still needs a completed secret-rotation window, production-readiness gate, authenticated deployed smoke run, backup restore drill, and visible operational alerts before a public commercial claim.
- The release quality gate now rejects missing, stale, unreviewed, or control-fixture evidence, but its `attestation_ref` is a redacted pointer rather than a cryptographically verified CI signature. A real release still needs retained CI artifacts and an auditable two-person review record.
- Object storage (MinIO/S3) must be configured for file uploads to persist beyond local disk.
- Celery Beat schedules attachment-retention cleanup and daily database backup. Backup success is not equivalent to a tested restore.

## Browser & Platform

- Public authentication and pricing routes have desktop Chromium and Pixel 7 smoke coverage. Authenticated project workflows, mobile review behavior, and non-Chromium browsers still need release evidence.
- Large document bundles (>50 files) may cause slow parsing or UI performance issues.
- The code editor (TipTap) does not support simultaneous multi-user editing.

## Commercial

- Stripe Checkout, Customer Portal redirection, signed webhook reconciliation,
  retry receipts, organization-scoped Checkout metadata, and subscription-item
  seat-quantity reconciliation are implemented in code. A retained Stripe
  Test Mode rehearsal, live operator configuration, support/finance procedures,
  and a reviewed migration path for historic user-level Stripe customers remain
  required before real payment processing is enabled.
- Durable organization memberships, organization subscription records, shared
  official-provider quota aggregation, server-side workspace entitlement
  resolution, seat-capacity enforcement during invitation acceptance,
  owner-only workspace billing authorization, and organization Stripe webhook
  reconciliation are now implemented. Seat overage is visible to the workspace
  owner and blocks new invitations, but Customer Portal quantity changes remain
  disabled until an explicit remediation workflow exists. Refunds, disputes, taxes, accounting
  exports, invoice archival, payment settlement reconciliation, and a webhook
  receipt retention job are not yet production-ready.
- Subscription plan enforcement covers project count and official-provider
  workflow, Assistant, and indexing quotas at organization scope. Export, BYOK,
  storage, collaboration, and complete per-feature entitlements still need a
  reviewed commercial policy.
