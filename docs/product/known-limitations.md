# Known Limitations (Pre-Pilot)

This document lists known limitations that must be acknowledged before onboarding pilot users.

## Authentication & Access

- Email verification is enforced at login; unverified users cannot authenticate. Admin can manually verify via `POST /auth/users/{id}/verify`.
- SMTP is configured (smtp.qq.com); verification and password-reset emails are delivered. Console fallback is used in test environments.
- Server-side refresh token storage with per-token revocation.
- Login rate limiting is in-memory only; it resets on server restart.

## AI & Generation

- AI generation requires a configured server-side provider API key for real output. Aliyun DashScope is configured as the domestic provider (`qwen3.5-flash` for LLM, `text-embedding-v4` for embeddings). Without a valid or IP-allowed key, worker adapters fall back to stub output for local safety.
- Generation quality depends on the provider model and prompt configuration; no automated quality gate exists yet.
- No automatic red-team or compliance scoring.
- Starter/free workflow usage is not yet backed by a durable usage ledger. The intended initial policy is 3 official-provider workflow draft runs per logged-in starter user, with assistant chat free but rate-limited.

## Review & Collaboration

- No real-time collaborative editing; users must refresh to see changes from others.
- Review threads are per-section only; no cross-section or document-level review threads.
- Review notification emails are sent on approve/reject decisions.

## Data & Export

- Data export includes all entity types (projects, bundles, documents, deliverables, sections, requirements, evidence, execution_runs, review_comments).
- DOCX export includes only approved sections; rejected or draft sections are excluded.
- PDF export available alongside DOCX.

## Operations

- No horizontal scaling strategy; the system runs as a single API process.
- Celery worker must be started separately; health-detailed endpoint includes worker status.
- Object storage (MinIO/S3) must be configured for file uploads to persist beyond local disk.
- Celery Beat schedules daily database backup at 3 AM.

## Browser & Platform

- The application targets desktop Chrome; mobile and other browsers are not tested.
- Large document bundles (>50 files) may cause slow parsing or UI performance issues.
- The code editor (TipTap) does not support simultaneous multi-user editing.

## Commercial

- Stripe integration is scaffolded but requires live keys for real payment processing.
- Subscription plan enforcement is limited to project count; no per-feature gating.
