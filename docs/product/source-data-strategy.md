# Source Data Strategy

## Goal

Define what kinds of source materials `DocPilot` should accept, how they should be prioritized, and what quality assumptions the system makes about them.

This document exists so future implementation does not treat "document upload" as a vague catch-all.

## Source categories

### Primary source categories for BidPilot

- request documents from the buyer or client
- presales input materials
- enterprise capability materials
- historical delivery and template materials
- policy, compliance, and qualification materials

### Examples

- RFP or tender files
- bid instructions
- scoring rules
- response templates
- company profile documents
- standard technical solution packs
- prior approved responses
- CV or staffing documents
- certifications and qualification files
- delivery methodology documents

## Intake model

All source data should enter the system through a `Bundle`.

A bundle is a project-scoped set of materials that may contain:

- one or more uploaded files
- optional future connectors or imports
- metadata about source type and intended usage

## Data source policy by phase

### Phase 0 and Phase 1

Support:

- manual file upload
- repeatable local seed bundles

Do not require:

- live third-party connectors
- enterprise document management integration

### Phase 2 and later

May expand to:

- connector-driven imports
- enterprise knowledge sources
- internal template libraries

## Data quality assumptions

The system must assume source quality varies.

Expected problems:

- scanned PDFs with OCR noise
- inconsistent headings
- partially structured tables
- duplicated content across files
- mixed Chinese and English content
- missing metadata

The system should normalize these issues as part of ingestion rather than assuming clean inputs.

## Priority order for source trust

When multiple sources conflict, prefer:

1. explicit request or tender documents
2. project-scoped approved materials
3. organization-approved reusable materials
4. generic templates or historical examples

If confidence is weak, the system should mark ambiguity rather than silently merging conflicting material.

## Local and staging data guidance

- keep one small public-safe seed bundle for repeatable developer validation
- keep one medium realistic bundle for staging acceptance
- ensure no customer-confidential material is required for baseline system validation
- when using public historical procurement material, track publisher URL,
  retrieval date, checksum, and source boundary separately from raw source
  bytes; do not commit third-party documents solely because they are publicly
  reachable

## Metadata expectations

Each `SourceDocument` should eventually track enough metadata to support:

- type classification
- origin classification
- project linkage
- trust level
- parser status
- language
- page count or equivalent size signals
- checksum and deduplication

## Future rule

If a new source category materially changes ingestion, trust ranking, or review behavior, update this document and the ingestion architecture docs in the same change.
