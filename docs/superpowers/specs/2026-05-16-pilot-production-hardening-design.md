# Pilot Production Hardening Design

- Status: Accepted
- Date: 2026-05-16

## Goal

Close remaining known limitations and production gaps before pilot exit, across 4 parallel streams.

## Stream 1: Backend Feature Completion

### 1.1 Review Notification Emails
- Listen on review decision events (approve/reject/comment)
- Reuse existing SMTP email backend (`app/email/`)
- Send email to project members when: section is approved, section is rejected with comments, new review comment added
- Email template: review_update with section name, decision, comment, project link

### 1.2 Data Export Completeness
- Expand `GET /auth/me/export` to include all entity types owned by user
- Add: deliverables, sections, review_comments, evidence_items, execution_runs
- JSON format, consistent with existing export shape

### 1.3 Worker Health Check
- Add Celery worker ping to `GET /ops/health-detailed`
- Check: worker process alive, queue backlog depth
- Return `worker: {status: "healthy"|"degraded"|"down", queue_depth: int}`

### 1.4 Refresh Token Server-Side Storage
- Add `refresh_token` table to models.py
- Store hashed refresh tokens on login
- Validate against DB on refresh
- Delete on logout; cascade delete expired tokens
- Migration generated via Alembic

### 1.5 Automated Backup Scheduling
- Add Celery Beat schedule for daily backup
- Configurable backup time via env var
- Task runs `scripts/backup.py` equivalent logic
- Log backup result to audit events

## Stream 2: Export Enhancement

### 2.1 PDF Export
- Use WeasyPrint for PDF generation
- HTML template → PDF conversion
- Same content source as DOCX export (approved sections)
- Endpoint: GET /export/deliverables/{id}/pdf
- Store PDF in MinIO, return download URL

### 2.2 Large Bundle Pagination
- Add pagination to GET /documents?bundle_id= with page/page_size
- Add streaming upload progress for large files
- Frontend: paginated document list with page controls

## Stream 3: Frontend Polish

### 3.1 Loading Skeletons
- Use shadcn Skeleton component for: project list, project detail tabs, review tab, audit tab, system tab
- Each page/feature gets a loading.tsx or inline skeleton

### 3.2 Error Boundary
- React error boundary at app shell level
- Catch unhandled render errors, show fallback UI with retry
- Per-route error boundaries for isolation

### 3.3 Empty States
- Consistent empty state pattern using shadcn Card + lucide icons
- ProjectListPage (no projects), Requirements (no requirements), Review (no sections), Audit (no events)

### 3.4 Toast Consistency
- Audit all toast usage: ensure sonner (or shadcn toast) used everywhere
- Consistent position, duration, style
- Error toasts: destructive variant; success: default

### 3.5 Responsive Polish
- Verify mobile sidebar collapse behavior
- Ensure tables are horizontally scrollable on small screens
- Form layouts adapt to narrow viewports

## Stream 4: E2E & Quality

### 4.1 E2E Tests
- Pricing page: tier display, current plan highlight, CTA navigation
- Account page: profile display, plan badge, admin controls
- Review reject-redraft cycle: reject → redraft → approve → export

### 4.2 API Error Standardization
- Consistent error response schema: {error: string, message: string, details?: any}
- Apply across all endpoints
- Test for error format consistency

### 4.3 Production Readiness Supplements
- Verify all env vars documented
- Check .env.example completeness
- Add missing config validation

## Testing Strategy

- Each stream writes unit + integration tests
- API changes: pytest fixtures + test files
- Frontend changes: vitest + testing-library
- E2E: Playwright tests
- All existing tests must continue passing

## Definition of Done

- Code implemented with tests
- All tests pass (API + frontend + E2E)
- Frontend typecheck passes
- Frontend build succeeds
- Release rehearsal passes
- known-limitations.md updated
