# BidBench and Requirement Ledger Foundation Implementation Plan

> This is the first implementation plan under the Product and Agent Re-foundation v2. Later subsystems receive separate plans after this phase establishes measurable truth.

## Goal

Create a reproducible quality baseline and turn the existing thin requirement records into the first useful Requirement Ledger and Bid Readiness Pack.

## Success Criteria

- A versioned fixture format describes sources, requirements, source locators, evidence, and expected coverage, with explicit development/regression/hidden dataset roles.
- A local command evaluates current extraction/retrieval output and emits machine-readable plus Markdown reports.
- Existing demo data becomes the first deterministic golden case without exposing customer data.
- Shared requirement records support provenance and ownership; BidPilot extension records support bid classification, coverage, evidence readiness, score, and risk.
- API users can list, filter, inspect, update, and bulk-assign requirements within tenant boundaries.
- The web project workspace exposes a usable Requirement Ledger and readiness summary.
- The Assistant can inspect the readiness summary through safe read-only capabilities. Mutations wait for the unified policy/capability runtime phase.
- Tests prove tenant isolation, schema migration, API behavior, benchmark scoring, and primary UI interactions.

## Assumptions

- The current `sample-data/bidpilot-demo` files appear intended as synthetic material but must be reviewed before normalization into tracked fixtures.
- PostgreSQL remains authoritative; benchmark expected outputs live as versioned fixture files.
- Phase 1 does not attempt production OCR bounding-box extraction for every file type. Locator schema supports it, while the first fixture may use page/section/text anchors.
- Phase 1 does not implement the full hybrid retrieval pipeline. It creates the evaluation interfaces that Phase 3 will use.
- The first demo fixture is a development baseline, not evidence for the final 95/90/98 quality targets.
- Customer-facing branding is BidPilot; reusable infrastructure and generic trace records remain scenario-neutral according to ADR 0003.

## Task 1: Define BidBench Contracts

Files:

- Create `packages/contracts/bidbench.py`
- Create `services/api/tests/bidbench/test_contracts.py`
- Update `packages/contracts/__init__.py`

Steps:

1. Write failing tests for dataset metadata, source records, requirement ground truth, locators, evidence links, and expected coverage states.
2. Add strict Pydantic v2 models with schema versioning.
3. Reject duplicate ids, unknown source references, invalid coverage states, and missing mandatory locators.
4. Run:

```powershell
uv run --directory services/api pytest tests/bidbench/test_contracts.py -q
```

Expected: all contract tests pass.

## Task 2: Create the First Golden Dataset

Files:

- Create `benchmarks/bidbench/v1/demo-smart-community/dataset.json`
- Create `benchmarks/bidbench/v1/demo-smart-community/sources/01-rfp.md`
- Create `benchmarks/bidbench/v1/demo-smart-community/sources/02-supplier-profile.md`
- Create `benchmarks/bidbench/v1/demo-smart-community/sources/03-reference-case.md`
- Create `benchmarks/bidbench/README.md`
- Update `.gitignore` only if generated reports need exclusion

Steps:

1. Review the current untracked demo files for secrets or personal data.
2. Normalize file names and copy only synthetic content into the benchmark directory using `apply_patch`.
3. Manually annotate mandatory requirements, scored requirements, deadlines, locators, known evidence, and deliberate missing-evidence cases.
4. Document matching rules, label guidelines, review status, licensing, provenance, fixture limitations, and contribution rules.
5. Validate the dataset through the Task 1 contract loader.

Expected: the development dataset loads deterministically and has no secret-like content. It is explicitly marked insufficient for release claims.

## Task 3: Implement Benchmark Scoring and Reporting

Files:

- Create `services/api/app/evaluation/__init__.py`
- Create `services/api/app/evaluation/bidbench.py`
- Create `services/api/app/evaluation/metrics.py`
- Create `services/api/tests/bidbench/test_metrics.py`
- Create `scripts/run_bidbench.py`
- Create `artifacts/bidbench/.gitkeep`

Steps:

1. Write failing metric tests for requirement recall, scoring recall, source association accuracy, evidence precision/recall, unsupported-claim rate, and combined completeness/traceability score.
2. Implement deterministic scoring independent of any model provider.
3. Add a runner that accepts dataset path and candidate result path.
4. Emit `report.json` and `report.md` under an ignored output directory.
5. Add an explicit threshold mode that returns non-zero on regression.
6. Run:

```powershell
uv run --directory services/api pytest tests/bidbench/test_metrics.py -q
uv run python scripts/run_bidbench.py --help
```

Expected: unit tests pass and CLI help renders.

## Task 4: Capture the Current Baseline Adapter

Files:

- Create `services/api/app/evaluation/adapters.py`
- Create `services/api/tests/bidbench/test_current_pipeline_adapter.py`
- Update `scripts/run_bidbench.py`

Steps:

1. Define a candidate-output protocol rather than coupling metrics to LangGraph.
2. Implement a deterministic fixture adapter first.
3. Add a current-pipeline adapter that can run against an existing project or saved output without requiring a live paid model in unit tests.
4. Store baseline report metadata: git commit, provider/model when present, prompt/version, timestamp, latency, and estimated cost.
5. Keep live provider execution opt-in through an explicit CLI flag.
6. Define artifact fields for prompt, model snapshot, run count, variance, matching policy, micro average, and macro average.
7. Add directory conventions for visible development outputs, frozen regression outputs, and externally controlled hidden acceptance outputs.

Expected: local tests never spend model credits, while an authorized operator can record a live baseline intentionally.

## Task 5: Add Shared Trace Models and BidPilot Requirement Extensions

Files:

- Update `packages/contracts/models.py`
- Update `services/api/app/requirements/schemas.py`
- Update `services/api/app/requirements/repository.py`
- Update `services/api/app/requirements/service.py`
- Add a new Alembic migration under `services/api/alembic/versions/`
- Update or create tests under `services/api/tests/requirements/`

Shared `RequirementItem` fields:

- `source_document_id`
- `source_locator_json`
- `original_text`
- `owner_user_id`
- `reviewer_user_id`
- `due_at`
- `verification_status`
- `extraction_confidence`
- `lock_version`
- `updated_at`

New shared trace records:

- `RequirementEvidenceLink`
- `Claim`
- `RequirementClaimLink`
- `ClaimEvidenceLink`
- `RequirementDecision` for explicit waiver, not-applicable, or accepted-risk decisions with reason and approver

New BidPilot extension record:

- `BidRequirementProfile`
- bid category/type
- mandatory flag
- score weight
- bid risk level
- system-derived coverage state
- system-derived evidence readiness
- bid deadline/submission metadata where applicable

Steps:

1. Write migration/model tests before editing the model.
2. Add conservative defaults compatible with existing rows.
3. Add indexes for project/type/coverage/risk/owner filters.
4. Validate referenced source documents and users belong to the same tenant/project context.
5. Recompute coverage from trace links and approved decisions; do not allow arbitrary direct writes to derived coverage.
6. Use optimistic concurrency for requirement updates and return conflict on stale versions.
7. Preserve existing API compatibility where practical.
8. Run migration upgrade/downgrade tests against a disposable database when available.

Expected: existing rows migrate safely and new invariants are enforced server-side.

## Task 6: Add Requirement Ledger APIs

Files:

- Update `services/api/app/requirements/router.py`
- Update `services/api/app/requirements/service.py`
- Update `services/api/app/requirements/repository.py`
- Update `services/api/app/requirements/schemas.py`
- Create `services/api/tests/requirements/test_requirement_ledger_api.py`

Endpoints or equivalent existing-route extensions:

- filtered project requirement list;
- requirement detail with evidence and source links;
- patch verification, risk, owner, reviewer, and due date;
- attach or remove evidence and claims;
- create reviewed waiver, not-applicable, or accepted-risk decisions;
- bulk assign and bulk verification updates;
- project readiness summary;
- export readiness matrix as CSV for debugging only; formal Pack export is Task 7.

Steps:

1. Write authentication and cross-tenant failure tests.
2. Add pagination and stable sorting.
3. Return user-facing enum values plus stable machine ids.
4. Add audit events for verification, ownership, trace links, decisions, and bulk changes.
5. Avoid returning raw embeddings or parser payloads.
6. Reject cross-project assignments and stale optimistic-lock versions.

Expected: API tests cover happy paths, invalid transitions, and tenant isolation.

## Task 7: Build and Export the Versioned Bid Readiness Pack

Files:

- Create `services/api/app/readiness/__init__.py`
- Create `services/api/app/readiness/schemas.py`
- Create `services/api/app/readiness/service.py`
- Create `services/api/app/readiness/router.py`
- Create `services/api/app/readiness/exporters.py`
- Update `services/api/app/main.py`
- Create `services/api/tests/readiness/test_readiness_summary.py`
- Create `services/api/tests/readiness/test_readiness_exports.py`

Steps:

1. Define a versioned Pack schema and deterministic calculations based on verified requirements, trace links, and approved decisions.
2. Report project summary, dates, qualifications, mandatory gaps, scored opportunities, evidence gaps, contradictions, overdue ownership, workload, and verification progress.
3. Keep any AI-generated narrative separate from deterministic scores and never present readiness as win probability.
4. Add source counts, formula version, generated timestamp, and provenance metadata.
5. Export a spreadsheet matrix and a Word executive report as durable artifacts.

Expected: readiness changes predictably as trace and decision records change; direct status editing cannot inflate it.

## Task 8: Add the Requirement Ledger UI

Files:

- Inspect existing project tab conventions before choosing exact paths.
- Create or update the project Requirements tab under `apps/web/src/features/projects/`
- Add API types/client methods under the existing web API layer
- Add locale keys under `apps/web/public/locales/en/` and `zh-CN/`
- Add component tests beside the feature

UI requirements:

- dense, business-readable table or grid;
- filters for type, coverage, evidence, risk, owner, and verification;
- source locator inspector without losing list context;
- bulk assignment and status actions;
- readiness summary and gap counts;
- responsive compact mode on narrow screens;
- no decorative animation that reduces scan speed.

Steps:

1. Write tests for filtering, source inspection, assignment, and empty/error states.
2. Reuse shadcn primitives and existing design tokens.
3. Use motion only for meaningful state transitions.
4. Verify desktop and mobile through Playwright CLI, not the Codex in-app browser.

Expected: a non-developer can identify the highest-risk missing requirement and assign it in under one minute.

## Task 9: Connect Read-Only Assistant Capabilities

Files:

- Update `services/api/app/assistant/tools.py`
- Update the capability registry path introduced or discovered during implementation
- Update `services/api/app/assistant/service.py`
- Update assistant UI tool labels/locales
- Add backend and frontend tests

Capabilities:

- inspect readiness summary;
- list high-risk or uncovered requirements;
- open a requirement/source locator;
- export the readiness matrix.

Steps:

1. Register these capabilities as safe reads under the existing boundary without introducing a second mutation policy.
2. Render localized user-facing execution summaries.
3. Never emit raw ORM/provider/tool payloads to chat.
4. Preserve chronological tool-before-answer streaming behavior.

Expected: the Agent can explain and navigate the first-day readiness flow without bypassing project authorization. Assignment and closure remain conventional UI actions until Phase 2 activates the unified write policy.

## Task 10: Phase Verification and Evidence

Files:

- Update `progress.txt`
- Create `docs/dev-log/2026-07-14-bidbench-requirement-ledger-foundation.md`
- Update product limitations if behavior changed

Commands:

```powershell
uv run --directory services/api pytest -q
pnpm --filter @docpilot/web test -- --run
pnpm --filter @docpilot/web build
uv run python scripts/run_bidbench.py --dataset benchmarks/bidbench/v1/demo-smart-community --candidate <saved-candidate-path>
```

Additional checks:

- migration upgrade from current production revision;
- cross-tenant API tests;
- Playwright desktop and mobile requirement flow;
- secret scan of changed files;
- independent code review;
- benchmark report archived in the release evidence path without committing model secrets or private documents.
- three-role collaboration test covering assignment, evidence contribution, reviewer rejection or closure, notification, stale update conflict, and audit.
- one representative ICP acceptance session measuring first-readiness time, useful omissions found, review effort, return intent, and willingness to pay.

Phase gate:

- The versioned Bid Readiness Pack works on the development dataset with Word and spreadsheet outputs.
- Current quality is measured honestly, including failed thresholds.
- The commercial wedge passes its Phase 1 user-validation gate or later platform work is paused for correction.
- The next plan is based on benchmark evidence rather than assumed architecture needs.
