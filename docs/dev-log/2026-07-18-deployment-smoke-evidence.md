# Deployment Smoke Evidence Artifact

- Date: 2026-07-18
- Scope: retain a safe, machine-readable result for the deployed API smoke check
- Status: implementation and focused verification complete

## Decision

`scripts/load_smoke.py` can now write a versioned JSON evidence artifact. It
contains only the normalized base URL, endpoint names, status codes, latency,
thresholds, and pass/fail result. Credential-bearing URLs, query strings, and
fragments are rejected before a request or artifact is written.

Production operators use `--require-https` and retain the artifact with the
release record. Local smoke behavior remains unchanged when the flag is absent.

## Verification

```powershell
uv run --directory services/api pytest tests/test_load_smoke_script.py -q
# 2 passed

uv run --directory services/api ruff check ../../scripts/load_smoke.py tests/test_load_smoke_script.py
# All checks passed
```
