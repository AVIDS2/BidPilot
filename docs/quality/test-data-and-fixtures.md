# Test Data and Fixtures

## Goal

Define how fixture data, sample bundles, and acceptance datasets should be managed.

This prevents the product from depending on ad hoc or private data during development.

## Fixture categories

### Unit fixtures

Small, focused fixtures used to validate:

- parser normalization helpers
- schema transforms
- adapter normalization
- UI state rendering

### Integration fixtures

Medium fixtures used to validate:

- API persistence flows
- worker execution flows
- object storage integration
- retrieval and evidence creation

### Acceptance fixtures

Project-like bundles used to validate the canonical end-to-end scenarios.

## Fixture rules

- prefer public-safe synthetic or sanitized material
- avoid customer-confidential material in the repository
- keep fixtures versioned and documented
- large benchmark datasets should not live in the main repo by default

## P0-B Fixed Synthetic Demo Pack

`sample-data/bidpilot-demo/manifest.json` is the canonical, de-identified
three-document material pack used by the P0 ingestion and presentation path.
It contains one RFP, one supplier capability document, and one case study.

- all material is repository-maintained synthetic demo content; it is not a
  customer bid or a claim about a real supplier
- the manifest declares a dataset id, version, role, expected structural
  anchors, and SHA-256 for every source file
- tests must verify the hashes before relying on the pack as a regression or
  demo input
- every parsed chunk derived from this pack must retain the stable locator
  contract: `source_document_id + chunk_index + source_checksum + document_version`
- a demo result can use sparse retrieval when no embedding provider is
  configured, but it must surface that degraded state rather than claiming a
  fully indexed live corpus

Update the manifest and its hash test in the same review whenever a fixture is
intentionally changed. Do not overwrite the files to make an evaluation score
look better; create a new dataset version instead.

## Recommended baseline packs

### Fixture Pack A: Tiny smoke bundle

Purpose:

- local smoke checks
- fast CI validation

Contents:

- one short PDF
- one short DOCX or markdown file
- one small image with OCR need

### Fixture Pack B: BidPilot realistic bundle

Purpose:

- staging acceptance scenario
- parsing and drafting validation

Contents:

- one RFP-like request document
- one requirements matrix or tabular file
- one template-like response structure
- one capability or company profile source

### Fixture Pack C: Public historical procurement rehearsal

Purpose:

- medium-corpus local or staging acceptance beyond a synthetic fixture
- PDF parsing, indexed retrieval, locator validation, and governed workflow
  rehearsal against publicly accessible historical procurement language

Contents:

- two historical public buyer RFPs
- one official public procurement reference document
- a checked-in source manifest with publisher URLs, byte lengths, SHA-256
  hashes, expected anchors, and retrieval checks

The repository tracks metadata only. The fetcher downloads source bytes into
ignored `tmp/` storage and fails closed when a publisher changes a document.
See [P0-D7 Public Procurement Rehearsal](public-procurement-rehearsal.md).

## Storage guidance

- lightweight fixtures may live in the repo
- heavier fixtures may live in controlled object storage or a separate internal artifact location
- fixture loading scripts should be deterministic

## BidBench Trace Maps

An offline BidBench run can normalize a saved Requirement Ledger snapshot through a reviewed trace map:

```json
{
  "source_document_ids": {
    "<platform source-document uuid>": "rfp"
  },
  "evidence_ids": {
    "<platform evidence uuid>": "ev-001"
  }
}
```

The map connects platform ids to frozen benchmark ids. It is authored or reviewed by a human evaluator; it must not be inferred from a filename, similarity search, or an LLM during scoring. Missing mappings deliberately produce no source or evidence credit.

Trace maps are evaluation artifacts, not customer data. A tracked map may contain only synthetic or approved public ids. Maps for private projects stay in controlled artifact storage together with the corresponding candidate, prompt/model metadata, and report; never store provider credentials, document bodies, or customer identifiers in them.

Use snapshot mode for an offline baseline without calling a provider:

```powershell
uv run python scripts/run_bidbench.py `
  --dataset benchmarks/bidbench/v1/demo-smart-community `
  --requirements-snapshot <saved-requirement-details.json> `
  --trace-map <reviewed-trace-map.json> `
  --candidate-id <stable-run-id> `
  --informational
```

The command saves `candidate.json`, `report.json`, and `report.md` under the ignored `output/bidbench/` directory so the same input can be scored again later.

## RetrievalBench

RetrievalBench evaluates the retrieval layer itself, separately from requirement
extraction and drafting. The visible development fixture is:

```text
benchmarks/bidbench/v1/demo-smart-community/retrieval-development.json
```

Each query declares an authorized project id, relevant frozen chunk ids,
expected source locators, whether the evidence is mandatory, and optional
expected degradation reasons. The fixture also repeats SHA-256 values for the
source files. The loader verifies those hashes before it permits scoring.

Captured runs record the retrieval profile, strategy (`dense`, `sparse`,
`fused`, or `reranked`), candidate limit, code/provider metadata, latency,
cost, per-query hits, and safe degradation categories. They must be produced
from the shared retrieval contract through an explicit source-document-id map;
the evaluator never guesses a source mapping from a filename or similarity.

Run a captured retrieval result without making any model call:

```powershell
uv run python scripts/run_retrieval_bench.py `
  --dataset benchmarks/bidbench/v1/demo-smart-community/retrieval-development.json `
  --run <captured-retrieval-run.json>
```

The report records Recall@1/3/5/10, MRR, locator validity, mandatory-evidence
recall, cross-project denial, and degraded-mode expectations. Comparing reports
with different dataset ids, fixture fingerprints, or retrieval profiles is
explicitly invalid. Development results are engineering evidence only, never a
commercial quality claim.

## MemoryBench

MemoryBench measures the governed-memory boundary separately from document
retrieval. Its visible synthetic development fixture is:

```text
benchmarks/bidbench/v1/demo-smart-community/memory-development.json
```

Each case defines an authorized organization, user, optional project, expected
record ids, forbidden record ids, a bounded item/character budget, and optional
degradation expectations. A captured run contains only record ids, scope
metadata, citation counts, character counts, and degradation categories. It
must not contain memory bodies, source document text, user prompts, provider
payloads, or credentials.

Run a captured, redacted result without any model call:

```powershell
uv run python scripts/run_memory_bench.py `
  --dataset benchmarks/bidbench/v1/demo-smart-community/memory-development.json `
  --run <captured-memory-run.json>
```

The report records expected-record recall, forbidden-record isolation,
provenance validity, user-private ownership correctness, context-budget
compliance, and required degraded-mode behavior. Reports with different fixture
fingerprints, policy versions, or retrieval profiles are intentionally not
comparable. Development fixtures provide engineering evidence, not commercial
accuracy claims.

## MemoryGraphBench

MemoryGraphBench evaluates a future reviewed entity/relation proposal path
before BidPilot materializes a project graph. The visible synthetic development
fixture is:

```text
benchmarks/bidbench/v1/demo-smart-community/memory-graph-development.json
```

Each case contains only opaque organization, project, memory-record, and
evidence identifiers plus reviewed expected entity types/names and relation
predicates. It must not contain customer document bodies, prompts, hidden model
reasoning, provider payloads, credentials, or raw production locators.

A captured run includes the scoped proposal JSON or a safe error code. It can
also carry redacted provider/model metadata, capture provenance, and aggregate
per-item reviewer-decision counts. The runner validates proposal shape,
declared entity endpoints, source-reference validity, entity/relation precision
and recall, and scope isolation without calling a provider:

```powershell
uv run python scripts/run_memory_graph_bench.py `
  --dataset benchmarks/bidbench/v1/demo-smart-community/memory-graph-development.json `
  --run <captured-memory-graph-run.json>
```

Add `--require-controlled-capture` only for a real, reviewed capture. That
mode requires a Git commit, provider and model metadata, non-control
provenance, and completed reviewer-summary coverage for every graph item. It
also fails on any schema, scope, or evidence-validity miss. It deliberately
does not set precision/recall thresholds: those must be calibrated on reviewed
regression data before graph materialization is considered.

`candidates/memory-graph-control.json` is a deterministic, fully scored
control fixture for validating the runner. It is intentionally marked
`control_fixture`, so it must fail `--require-controlled-capture` even when all
quality metrics are 100%.

Development outputs are engineering evidence only. A graph materialization or
retrieval release needs reviewed regression/hidden fixtures and a demonstrated
user-decision improvement; it may not be promoted from a visual demo alone.

## AssistantBench

AssistantBench evaluates the bounded Agent router and Runtime policy boundary,
not free-form response prose. A case records synthetic/public user text, an
optional opaque project context, the expected capability or missing input, and
the expected approval/typed-confirmation decision. A candidate records only
its structured intent, argument keys, selected opaque project scope, and policy
outcome; it never stores hidden reasoning, raw tool output, or chat history.

The visible development fixture is:

```text
benchmarks/bidbench/v1/demo-smart-community/assistant-development.json
```

Run the offline scorer with a redacted capture:

```powershell
uv run python scripts/run_assistant_bench.py `
  --dataset benchmarks/bidbench/v1/demo-smart-community/assistant-development.json `
  --run <captured-assistant-run.json>
```

The scorer checks intent mode, capability routing, missing-input handling,
required argument keys, runtime-policy parity, destructive typed confirmation,
project-scope safety, and unknown capabilities. Add
`--require-controlled-capture` only for a real reviewed capture; it rejects
missing commit/provider/model/provenance metadata and any policy, confirmation,
or scope-safety miss. It intentionally does not guess task-success thresholds
from the development fixture.

`candidates/assistant-control.json` is a deterministic control fixture. It
must fail controlled-capture mode even with 100% scores because its provenance
is explicitly `control_fixture`.

For an actual reviewed Operator capture, keep the case-to-runtime mapping in a
restricted manifest outside the repository and run:

```powershell
uv run python scripts/capture_assistant_runtime_bench.py `
  --dataset <assistant-regression-or-hidden.json> `
  --manifest <private-runtime-capture-manifest.json> `
  --confirm-redacted-runtime-capture `
  --output-file output/assistant-runtime-capture/candidate-run.json
```

The command reads only durable plan/action/approval records and writes a
candidate with no messages, argument values, runtime ids, checkpoint data, raw
tool output, or provider payloads. The manifest may contain opaque run/project
ids for the approved test environment and must remain in controlled storage.
Score the generated candidate with `run_assistant_bench.py`, then retain the
reviewed report with the release evidence set.

## Unified quality gate

`benchmarks/bidbench/release-quality-gate-v1.json` is the reviewed policy that
combines one BidBench, RetrievalBench, MemoryBench, and AssistantBench report. The policy is
deliberately stored separately from individual reports so threshold changes are
visible in code review.

Use development mode while building the benchmark pipeline. It applies the same
metrics but marks the artifact as not release-eligible:

```powershell
uv run python scripts/run_quality_gate.py `
  --policy benchmarks/bidbench/release-quality-gate-v1.json `
  --bidbench-report <bidbench-report.json> `
  --retrieval-report <retrieval-report.json> `
  --memory-report <memory-report.json> `
  --assistant-report <assistant-report.json> `
  --mode development
```

Release mode requires reports generated from `regression` or `hidden` fixtures,
a common explicit Git commit, and one shared, redacted evidence chain. It
rejects development fixtures, missing commit metadata, stale reports, control
fixtures, single-review evidence, missing attestations, mismatched evidence
sets, and safety/traceability regressions.

Add the following `provenance` object to the saved BidBench candidate or the
captured RetrievalBench/MemoryBench run before scoring it. These identifiers
are intentionally opaque: do not put source text, prompts, reviewer names,
provider payloads, or credentials in them.

```json
{
  "evidence_set_id": "release-2026-07-18-rc1",
  "capture_id": "release-2026-07-18-rc1-capture",
  "capture_kind": "current_pipeline",
  "review_level": "two_person_review",
  "evaluator_version": "bidpilot-evaluation-v1",
  "attestation_ref": "ci:github-actions-run-123456"
}
```

All four reports must use the same `evidence_set_id` and `capture_id`. Retain
the actual CI artifact and review record in controlled storage; the contract
carries only a redacted pointer and is not itself a cryptographic signature.

```powershell
uv run python scripts/run_quality_gate.py `
  --policy benchmarks/bidbench/release-quality-gate-v1.json `
  --bidbench-report <bidbench-regression-report.json> `
  --retrieval-report <retrieval-regression-report.json> `
  --memory-report <memory-hidden-report.json> `
  --assistant-report <assistant-regression-report.json> `
  --mode release `
  --expected-git-commit <release-commit>
```

The output is an audit artifact under `output/quality-gate/`. Keep private
fixtures and their reports in controlled CI artifact storage. Never add source
document text, prompts, provider responses, user identifiers, or credentials to
the policy or report files.

## Documentation rule

If a new acceptance scenario requires a new canonical data shape, update this document and the acceptance-scenarios doc together.
