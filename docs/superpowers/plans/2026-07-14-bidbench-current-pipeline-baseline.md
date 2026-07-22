# BidBench Current Pipeline Baseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert a saved current Requirement Ledger snapshot into an honest, versioned BidBench candidate and report without inventing source or evidence traceability.

**Architecture:** The adapter accepts the existing Requirement API detail shape plus an explicit trace-map artifact. The map translates platform UUIDs to frozen BidBench source/evidence ids. Missing mappings never receive evaluation credit; mapped unknown evidence remains visible as a false positive. The CLI can either score a saved candidate or normalize a snapshot, archive the normalized candidate next to the report, and apply the same threshold policy.

**Tech Stack:** Python 3.12, Pydantic v2, existing `contracts.bidbench`, pytest, argparse.

---

## File Map

- `packages/contracts/bidbench.py`: allow `accepted_risk` as a governed coverage outcome shared with the Requirement Ledger.
- `services/api/app/evaluation/adapters.py`: parse current requirement-detail snapshots, explicit trace maps, and normalize them into `BidBenchCandidate`.
- `services/api/tests/bidbench/test_current_pipeline_adapter.py`: define conversion and no-false-credit behavior before implementation.
- `services/api/tests/bidbench/test_contracts.py`: verify the contract accepts accepted-risk coverage.
- `scripts/run_bidbench.py`: add snapshot-mode CLI arguments and archive the normalized candidate with the report.
- `services/api/tests/bidbench/test_runner.py`: exercise both saved-candidate and snapshot report paths without provider calls.
- `docs/quality/test-data-and-fixtures.md`: document trace-map artifacts and baseline evidence retention.

## Task 1: Align the Benchmark Coverage Contract

**Files:**
- Modify: `packages/contracts/bidbench.py`
- Modify: `services/api/tests/bidbench/test_contracts.py`

- [x] **Step 1: Add a failing contract test for the existing accepted-risk ledger outcome.**

```python
def test_candidate_accepts_accepted_risk_coverage() -> None:
    candidate = BidBenchCandidate.model_validate({
        "schema_version": "1.0",
        "dataset_id": "fixture",
        "candidate_id": "accepted-risk",
        "system_name": "unit-test",
        "requirements": [{
            "id": "candidate-req-1",
            "normalized_text": "Explicitly accepted risk",
            "requirement_type": "technical",
            "coverage_status": "accepted_risk",
        }],
    })
    assert candidate.requirements[0].coverage_status == "accepted_risk"
```

- [x] **Step 2: Run the focused test and verify it fails because `CoverageStatus` does not yet contain `accepted_risk`.**

```powershell
uv run --directory services/api pytest tests/bidbench/test_contracts.py::test_candidate_accepts_accepted_risk_coverage -q
```

- [x] **Step 3: Add `ACCEPTED_RISK = "accepted_risk"` to `CoverageStatus`.**

```python
class CoverageStatus(StrEnum):
    UNCOVERED = "uncovered"
    PARTIAL = "partial"
    COVERED = "covered"
    DISPUTED = "disputed"
    NOT_APPLICABLE = "not_applicable"
    ACCEPTED_RISK = "accepted_risk"
```

- [x] **Step 4: Re-run the focused contract suite.**

```powershell
uv run --directory services/api pytest tests/bidbench/test_contracts.py -q
```

## Task 2: Normalize the Current Requirement Detail Snapshot

**Files:**
- Modify: `services/api/app/evaluation/adapters.py`
- Modify: `services/api/tests/bidbench/test_current_pipeline_adapter.py`

- [x] **Step 1: Add failing tests for a full Requirement API detail snapshot with explicit source/evidence trace maps.**

```python
trace_map = CurrentPipelineTraceMap(
    source_document_ids={"source-db-1": "rfp"},
    evidence_ids={"evidence-db-1": "ev-001"},
)
candidate = build_candidate_from_requirement_snapshot(
    snapshot_path=snapshot_path,
    dataset_id="demo-smart-community",
    candidate_id="current-project-1",
    trace_map=trace_map,
)
assert candidate.requirements[0].requirement_type == "qualification"
assert candidate.requirements[0].locators[0].source_id == "rfp"
assert candidate.requirements[0].evidence_ids == ["ev-001"]
assert candidate.claims[0].accepted is True
```

- [x] **Step 2: Add a failing no-false-credit test for a snapshot without a source map.**

```python
candidate = build_candidate_from_requirement_snapshot(
    snapshot_path=snapshot_path,
    dataset_id="demo-smart-community",
    candidate_id="unmapped",
)
assert candidate.requirements[0].locators == []
assert candidate.requirements[0].evidence_ids == []
```

- [x] **Step 3: Add typed snapshot and trace-map models.**

```python
class CurrentPipelineTraceMap(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    source_document_ids: dict[str, str] = Field(default_factory=dict)
    evidence_ids: dict[str, str] = Field(default_factory=dict)
```

The requirement model must parse `bid_profile`, `source_document_id`, `source_locator_json`, `evidence_links`, and `claims`. Preserve old list and `{ "requirements": [...] }` snapshot formats.

- [x] **Step 4: Convert only verifiable trace fields.**

```python
source_id = trace_map.source_document_ids.get(requirement.source_document_id or "")
locators = [_to_locator(requirement.source_locator_json, source_id)] if source_id else []
evidence_ids = [
    trace_map.evidence_ids[link.evidence_id]
    for link in requirement.evidence_links
    if link.relation_type == "supports" and link.evidence_id in trace_map.evidence_ids
]
```

Map known bid categories to `RequirementType`, derive `is_mandatory` from the profile before falling back to priority, preserve verified claims as `accepted=True`, and reject malformed mapped locators with an actionable `ValueError`.

- [x] **Step 5: Run adapter tests.**

```powershell
uv run --directory services/api pytest tests/bidbench/test_current_pipeline_adapter.py -q
```

## Task 3: Add a Reproducible Snapshot-Mode CLI

**Files:**
- Modify: `scripts/run_bidbench.py`
- Modify: `services/api/tests/bidbench/test_runner.py`
- Modify: `docs/quality/test-data-and-fixtures.md`

- [x] **Step 1: Add failing CLI tests for snapshot mode.**

```python
result = subprocess.run([
    sys.executable, "scripts/run_bidbench.py",
    "--dataset", str(dataset_dir),
    "--requirements-snapshot", str(snapshot_path),
    "--candidate-id", "current-project-1",
    "--trace-map", str(trace_map_path),
    "--informational",
], capture_output=True, text=True)
assert result.returncode == 0
assert (output_dir / "candidate.json").is_file()
```

- [x] **Step 2: Make `--candidate` and `--requirements-snapshot` mutually exclusive.**

```python
candidate_input = parser.add_mutually_exclusive_group(required=True)
candidate_input.add_argument("--candidate", type=Path)
candidate_input.add_argument("--requirements-snapshot", type=Path)
parser.add_argument("--trace-map", type=Path)
parser.add_argument("--candidate-id")
```

- [x] **Step 3: For snapshot mode, load the dataset id, normalize a candidate, score it through the existing evaluation path, and write a canonical `candidate.json` alongside `report.json` and `report.md`.**

```python
if args.requirements_snapshot:
    candidate = build_candidate_from_requirement_snapshot(...)
    candidate_path.write_text(candidate.model_dump_json(indent=2), encoding="utf-8")
report = evaluate_files(args.dataset, candidate_path)
```

Use a temporary file for scoring before the fingerprinted output directory exists; then copy the exact bytes to the final output directory. Do not call a model provider.

- [x] **Step 4: Document the trace-map JSON shape and retention rule.**

```json
{
  "source_document_ids": {"<platform source-document uuid>": "rfp"},
  "evidence_ids": {"<platform evidence uuid>": "ev-001"}
}
```

The map is a derived evaluation artifact. It may contain internal ids but never provider keys, customer document content, or secrets; keep it out of public benchmark directories unless its data is synthetic.

- [x] **Step 5: Run all BidBench tests and one offline development report.**

```powershell
uv run --directory services/api pytest tests/bidbench -q
uv run python scripts/run_bidbench.py --dataset benchmarks/bidbench/v1/demo-smart-community --candidate benchmarks/bidbench/v1/demo-smart-community/candidates/empty-control.json --informational
```

## Task 4: Record the Baseline Boundary

**Files:**
- Modify: `docs/dev-log/2026-07-14-bidbench-requirement-ledger-foundation.md`
- Modify: `progress.txt`

- [x] **Step 1: Record the development-only empty-control report and state that it is a harness smoke baseline, not a commercial quality claim.**

- [x] **Step 2: Record that a live general-AI comparison is opt-in and requires a separately approved provider run, saved prompt/version metadata, and a reviewed trace map.**

- [x] **Step 3: Run `git diff --check`, the backend test suite, web tests, and web build before marking this sub-plan complete.**

> **Implementation status (2026-07-14):** Tasks 1–4 are complete as a development harness. The commercial phase gate remains open: no authorized live-provider comparison, hidden/frozen regression set, three-role collaboration session, or ICP acceptance session has been recorded. These are product-validation evidence, not work inferred from a green unit-test suite.
