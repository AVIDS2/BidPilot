# P0-D8 Role-Aware Bid Rehearsal

## Purpose

This controlled acceptance path closes the semantic gap between a buyer's RFP
and a supplier's supporting material. It runs against the same local API,
Celery Worker, LangGraph workflow, Postgres control plane, object storage, and
review APIs as a normal project.

It is deliberately separate from the public-material rehearsal:

- P0-D7 proves that the system can process pinned public procurement PDFs.
- P0-D8 proves that buyer obligations are not confused with supplier claims,
  and that an authorized reviewer can close a requirement through evidence and
  claim verification.

## Fixture and source roles

The tracked, de-identified fixture is
[`sample-data/bidpilot-demo/manifest.json`](../../sample-data/bidpilot-demo/manifest.json).
It is fictional engineering material, not a real solicitation, supplier,
customer, certification, or performance claim.

| Bundle source type | Documents | Allowed product effect |
| --- | --- | --- |
| `buyer_rfp` | RFP | Parse, index, retrieve, and materialize Requirement Ledger rows. |
| `supplier_evidence` | Capability statement and case study | Parse, index, retrieve, and become Evidence; never materialize buyer requirements. |

`upload` and `assistant_upload` remain legacy-compatible requirement-eligible
types. New production flows must use an explicit `buyer_rfp` or
`supplier_evidence` role rather than a generic mixed bundle.

## Procedure

1. Start the local API, Worker, PostgreSQL, Redis, and MinIO stack.
2. Run the rehearsal only against loopback services and the local `docpilot`
   database:

```powershell
$env:DOCPILOT_DATABASE_URL = "postgresql+psycopg://docpilot:docpilot@127.0.0.1:5433/docpilot"
uv run --directory services/api --locked --no-sync python ../../scripts/run_bidpilot_hybrid_rehearsal.py
```

3. Inspect the ignored redacted artifact at
`tmp/p0-d8-role-aware-rehearsal.json`.

The runner creates an isolated verified actor, organization, project, role-aware
bundles, workflow runs, and review records. It does not target remote API or
database hosts. It uses direct persistence only to create the isolated verified
test actor and controlled failed retry source; every business operation is
performed through the public API.

## Acceptance checkpoints

1. The buyer RFP produces at least five durable, source-backed Requirement
   Ledger rows.
2. No requirement row is sourced from either supplier-evidence document.
3. A real LangGraph `past-performance` draft reaches human review and creates
   an Evidence record sourced from the fictional case study.
4. The runner links that Evidence to the declared buyer requirement through
   `POST /requirements/{id}/evidence`, verifies the link, creates a factual
   Claim, and verifies the Claim through the public API.
5. The selected Requirement becomes `covered` with `sufficient` evidence, and
   `GET /readiness/projects/{project_id}` reports at least one covered row.
6. The workflow still completes reject -> redraft -> approve -> approved-only
   export -> controlled retry without bypassing human review.

## Boundary

This proves data role separation and governed human verification. It does not
claim that automatic retrieval alone establishes legal, commercial, or
procurement sufficiency. A reviewer remains accountable for whether a specific
supplier fact supports a specific buyer obligation.
