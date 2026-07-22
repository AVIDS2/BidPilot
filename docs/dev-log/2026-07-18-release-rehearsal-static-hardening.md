# Release Rehearsal Static Hardening

- Date: 2026-07-18
- Scope: make the local release rehearsal validate static quality across API and Worker execution paths
- Status: local evidence complete; production promotion remains blocked on production-only evidence

## Delivered

1. Added Ruff checks for both API and Worker to `scripts/release_rehearsal.py` and documented them in the release runbook.
2. Added Worker Ruff as an explicit development dependency and refreshed the workspace lock file.
3. Updated the GitHub release workflow so its backend job runs the same migration, API Ruff/API tests, and Worker Ruff/Worker tests sequence as the local rehearsal.
4. Removed safe unused imports and dead test scaffolding. The former Worker graph "integration" test only applied mocks and ended with `pass`; it was removed rather than preserving fake coverage.
5. Preserved two real public module contracts that static import cleanup can otherwise erase:
   - `app.db.Base` remains an explicit shared declarative-metadata export for Alembic and service tests.
   - Worker `provider_env` explicitly re-exports shared embedding configuration helpers consumed by the embedding adapter.
5. Added a focused API test for the `Base` metadata export. The full release rehearsal exercises the Worker export through retrieval, memory, and task test collection.

## Verification Evidence

```powershell
uv run --directory services/api ruff check app tests
# All checks passed

uv run --directory services/worker ruff check app tests
# All checks passed

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

## Remaining Production Evidence

1. Run the release quality gate using reviewed `regression` or `hidden` BidBench, RetrievalBench, and MemoryBench reports from the actual release commit.
2. Inject production-shaped secrets and pass `scripts/production_readiness.py --target production`.
3. Run authenticated deployed browser smoke, backup-restore drill, and operational alert verification before a commercial launch claim.
