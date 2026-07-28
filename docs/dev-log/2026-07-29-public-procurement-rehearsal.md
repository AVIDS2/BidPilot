# Public Procurement Rehearsal Acceptance

Date: 2026-07-29

## Scope

Validated the P0-D7 public historical procurement rehearsal against the local
BidPilot API, Worker, PostgreSQL, Redis, MinIO, configured chat provider, and
configured embedding provider.

The source pack contains metadata only in Git. The three historical public PDFs
were fetched into ignored `tmp/` storage after SHA-256 and PDF-signature
validation.

## Result

The run passed all ten checkpoints:

1. isolated verified user and organization created
2. isolated project and default deliverable created
3. three public PDFs uploaded through the normal document API
4. real Worker parsing and 1536-dimension indexing completed
5. source-specific retrieval checks returned the expected documents with
   non-invalid locators
6. LangGraph drafting reached durable human review
7. the first immutable candidate was rejected and a replacement candidate was
   created
8. the replacement was approved and an approved-only DOCX export was produced
9. a controlled failed execution was retried through the public execution API
   and returned to human review before approval
10. both governed execution paths reached success

The accepted export measured 39,645 bytes. The ignored local evidence artifact
is `tmp/p0-d7-public-rehearsal.json`; it records IDs, counts, checksums,
methods, statuses, and step outcomes only.

## Verification

- API tests: `8 passed`
- Worker ingestion and indexing tests: `11 passed`
- Ruff for the rehearsal scripts and test: passed

## Boundary

This validates engineering behavior with public historical procurement
documents. It does not assert that any solicitation remains current, that any
supplier is qualified, or that generated material is legally compliant.
