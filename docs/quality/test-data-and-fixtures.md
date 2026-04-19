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

## Storage guidance

- lightweight fixtures may live in the repo
- heavier fixtures may live in controlled object storage or a separate internal artifact location
- fixture loading scripts should be deterministic

## Documentation rule

If a new acceptance scenario requires a new canonical data shape, update this document and the acceptance-scenarios doc together.
