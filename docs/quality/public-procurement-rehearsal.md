# P0-D7 Public Procurement Rehearsal

## Purpose

This rehearsal proves that the governed BidPilot backend can process a medium,
publicly accessible procurement corpus through the same API, Worker, retrieval,
LangGraph, human review, export, and retry boundaries used by the synthetic
Golden Path.

It is engineering evidence, not a claim that BidPilot has produced a compliant
or competitive bid for any live procurement.

## Source policy

The tracked pack is [`sample-data/bidpilot-public-rehearsal/manifest.json`](../../sample-data/bidpilot-public-rehearsal/manifest.json).
It records source metadata, source URLs, byte lengths, and SHA-256 hashes. Raw
source files are never committed. The fetcher writes them under ignored
`tmp/p0-d7-public-rehearsal/` only after the pinned hash matches.

| Material | Role | Publisher | Why it is included |
| --- | --- | --- | --- |
| State Bar of California General Office Supplies RFP | historical buyer RFP | State Bar of California | Tests scope, submission, and evaluation language in a compact real RFP. |
| Office of Homeless Youth Criminal Justice Training RFP | historical buyer RFP | Washington State Department of Commerce | Tests a longer RFP with schedule, proposal content, evaluation, and public disclosure sections. |
| RFP/RFI sample language for LMR subscriber units | public procurement reference | CISA | Tests structured requirements, scoring, qualifications, and training language. |

The source URLs are public historical documents, but their publishers retain
their own terms. The project does not redistribute those bytes. Review current
publisher terms before any use outside this narrow local or staging rehearsal.

## Reproducible procedure

1. Start the local API, Worker, PostgreSQL, Redis, and MinIO stack.
2. Fetch and pin-check the public sources:

```powershell
uv run --directory services/api --locked --no-sync python ../../scripts/fetch_bidpilot_public_rehearsal.py
```

3. Point the runner at the local application database and run the rehearsal:

```powershell
$env:DOCPILOT_DATABASE_URL = "postgresql+psycopg://docpilot:docpilot@localhost:5433/docpilot"
uv run --directory services/api --locked --no-sync python ../../scripts/run_bidpilot_public_rehearsal.py
```

4. Inspect the ignored artifact at `tmp/p0-d7-public-rehearsal.json`.

The runner refuses remote API and database targets. It creates an isolated
verified actor, organization, project, and bundle, so it does not mutate a
real user or project.

## Acceptance checkpoints

1. Each public source has a verified pinned SHA-256 and PDF signature.
2. All three documents are uploaded through `POST /documents/upload` and reach
   `parse_status=parsed` plus `index_status=indexed` through the real Worker.
3. Three retrieval queries resolve to their expected source documents with a
   non-invalid locator status; the evidence artifact stores only document IDs,
   methods, and locator status.
4. A real LangGraph draft reaches durable human review; the first candidate is
   rejected, a new immutable candidate is created, the revision is approved,
   and the approved-only DOCX export is non-empty.
5. A controlled local failed run is retried through the public execution API,
   returns to human review, is approved, and reaches `succeeded`.

## What this does not prove

- The historical RFP deadlines, scope, contact details, pricing, or legal terms
  are current or applicable to another procurement.
- The pack contains no real supplier response, therefore it cannot prove a
  supplier-capability claim or an award outcome.
- This is not legal review, procurement approval, customer UAT, or production
  readiness by itself. It supplements the synthetic Golden Path, security
  suite, evaluation reports, and release rehearsal.

## Source changes

If a source changes, the fetcher fails closed. Do not overwrite the source or
quietly update its hash. Review the changed material first, then create a new
dataset version and preserve the former manifest for comparable evidence.
