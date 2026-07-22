# BidBench and Requirement Ledger Foundation: Delivery Log

- Date: 2026-07-14
- Scope: offline quality baseline and Requirement Ledger/Readiness foundations
- Status: development benchmark harness strengthened; live comparison and dataset expansion remain planned work

## What Exists

BidPilot now has a synthetic development dataset, versioned Pydantic contracts, deterministic requirement/evidence/claim metrics, threshold support, a Requirement Ledger, Readiness Pack exports, and a project workbench. The development corpus is intentionally not a commercial accuracy claim.

The current refinement closes the gap between the ledger and the benchmark:

1. `accepted_risk` is now an explicit benchmark coverage outcome, matching the approved decision state used by the Requirement Ledger and readiness calculations.
2. A saved Requirement Ledger detail snapshot can be normalized into a `BidBenchCandidate`.
3. Source document and evidence UUIDs receive benchmark credit only through a human-reviewed trace map.
4. The CLI can score either a saved candidate or a ledger snapshot, and archives the exact normalized `candidate.json` with `report.json` and `report.md`.
5. All of this is offline. The runner never sends a source document or provider credential to a model.

## First Harness Control

The synthetic `empty-control` candidate was scored through the CLI in informational mode. It produced a combined score of `0.00%`, as expected for an empty extraction. This is a smoke/control result proving the scoring path can report a failure honestly. It is not a statement about product quality, user value, or a general-AI comparison.

## How a Real Baseline Is Captured

1. Run the current requirement extraction path for one reviewed synthetic or authorized dataset.
2. Save the resulting requirement-detail responses without keys or private source bodies.
3. Review a trace map from platform source/evidence ids to frozen BidBench ids.
4. Run `scripts/run_bidbench.py --requirements-snapshot ... --trace-map ... --candidate-id ... --informational`.
5. Retain the generated candidate, report, provider/model/prompt metadata, and source hashes together in controlled artifacts.
6. Run a carefully prompted general-purpose AI baseline on the same frozen inputs only through an explicitly authorized provider job. Compare reports; do not rely on remembered chat output.

## Current Limits

- The repository has one synthetic visible development set. It cannot support release-quality targets or commercial claims.
- No live general-AI/provider baseline has been run in this phase, so no comparative claim is made.
- The snapshot adapter is intentionally an artifact adapter. It does not replace a future correlated production trace exporter.
- Hybrid retrieval, reranking, and citation validation will use this benchmark interface in their own phase.

## Assistant Read-Only Readiness Surface

The Assistant can now safely inspect a project readiness summary, enumerate high-risk or category-specific readiness gaps, and open the provenance locator for a requirement. These capabilities are registered in both the deterministic local runtime and the LangGraph operator runtime, require normal project read access, and stream the tool result before the conversational answer. The UI renders localized user-facing labels rather than raw tool or ORM payloads.

Readiness-pack creation/export and every write action remain outside this surface. They will be attached to the unified policy and approval runtime rather than creating a second mutation path.

## Test Database Discipline

Route tests no longer create ORM tables directly. Tests now require a database that has been upgraded through Alembic, matching CI and deployment behavior. This prevents a test run against a developer database from creating tables without the corresponding Alembic revision and later blocking a normal upgrade.

## Learning Note

An **offline benchmark** is not a prompt demo. Its inputs, labels, matching policy, source hashes, candidate output, formulas, and thresholds must all be versioned. A system earns credit for a citation only when the evaluator can map its platform record to the frozen benchmark evidence; guessing a source would make the number look better while making it less trustworthy.
