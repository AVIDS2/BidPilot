# Release Evidence Provenance

- Date: 2026-07-18
- Scope: prevent release-quality reports from becoming false-green JSON files
- Status: implementation and local regression verification complete; production promotion remains blocked on real evidence

## Decision

Development fixtures remain easy to run without provenance. Release promotion is
stricter: every BidBench, RetrievalBench, and MemoryBench report must describe
one redacted evidence chain from the release commit.

The shared contract records only opaque identifiers:

- `evidence_set_id` joins the three reports.
- `capture_id` identifies the current-pipeline or reviewed-snapshot capture.
- `capture_kind` excludes control fixtures from release promotion.
- `review_level` requires two-person review by default.
- `attestation_ref` points to retained CI or review evidence outside the repo.
- `evaluator_version` identifies the scoring harness.

No customer text, prompts, provider payloads, reviewer identities, keys, or
credentials are permitted in the contract.

## Enforcement

Release mode rejects missing provenance, `control_fixture` captures,
single-review evidence, missing attestations, stale or timezone-less reports,
mismatched evidence sets or capture identifiers, and missing BidBench
provider/model/prompt metadata. The maximum report age is seven days and the
minimum evidence controls cannot be disabled by a policy file.

The contract is optional for development reports, so local benchmark work stays
backward-compatible. It propagates from a BidBench candidate or a
RetrievalBench/MemoryBench run into the scored report and then into the unified
quality-gate artifact.

## Residual Limit

`attestation_ref` is deliberately a redacted pointer, not a cryptographic
signature verifier. Before a commercial release, the named release owner must
retain and review the actual CI artifact, review record, and private
regression/hidden fixture evidence.

## Verification Evidence

```powershell
uv run --directory services/api pytest tests/evaluation tests/bidbench -q
# 55 passed

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

An independent read-only Claude review found no concrete release-gate bypass.
Its residual trust-boundary observations are recorded above and the policy was
subsequently tightened so release policies cannot disable two-person review,
attestation, shared capture linkage, or the seven-day freshness limit.
