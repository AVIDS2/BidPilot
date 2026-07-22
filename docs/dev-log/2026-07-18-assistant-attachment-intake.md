# Governed Assistant Attachment Intake

- Date: 2026-07-18
- Scope: make uploaded Assistant files durable, owner-scoped, project-ingestable, and retention-bounded
- Status: implementation and local verification complete; production rollout still requires normal migration/release evidence

## Delivered

1. `assistant_attachment` is a PostgreSQL-owned staging record. It keeps the uploader/org boundary, private staging key, SHA-256, bounded server-side extracted text, expiration, and eventual project/bundle/document links.
2. `POST /assistant/attachments` now stores the raw file in private MinIO staging before returning an opaque attachment ID. The browser never receives extracted document text.
3. Incoming assistant turns hydrate attachment context from the owner-scoped database record. Browser-provided filenames and extracted text cannot override server records.
4. The runtime capability `attach_uploaded_documents` is a costing, approval-gated action. It copies selected staged files into a project bundle, emits audit and usage events, and queues the existing ingestion worker.
5. The LangGraph Operator state preserves attachment IDs across a project-creation approval. A follow-up capability can attach the same files after the new project exists without relying on client memory.
6. Direct browser document upload can consume the matching staged record through its checksum, so the temporary object is not retained twice.
7. The Worker now expires unused staging records and retries staging-object deletion hourly through a dedicated `worker-beat` service.

## Verification Evidence

```powershell
uv run --directory services/api alembic upgrade head
# d0e1f2a3b4c5 (head)

uv run --directory services/api pytest -q
# 487 passed

uv run --directory services/worker pytest -q
# 78 passed

pnpm --filter @docpilot/web test -- --run
# 25 files, 89 tests passed

pnpm --filter @docpilot/web build
# passed

python -u scripts/release_rehearsal.py --run
# migrations, API/Worker Ruff checks, API 487, Worker 78,
# frontend typecheck, 25 Vitest files / 89 tests, and production build passed
```

The focused regression covers owner isolation, browser-text spoofing resistance, expiry rejection, direct browser handoff, project ingestion, and the three-approval LangGraph path from project creation through document ingestion to readiness-pack generation. Artifact results expose only authenticated download paths to the browser.

## Remaining Production Evidence

1. Bring up `worker-beat` in staging and verify one real expired staging object is deleted without affecting a project `SourceDocument`.
2. Retain release-quality gate reports from reviewed regression or hidden fixtures before promotion; development fixture reports remain non-release evidence.
