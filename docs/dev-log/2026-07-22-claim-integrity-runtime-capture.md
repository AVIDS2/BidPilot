# Claim Integrity Runtime Capture

## Goal

Make the structural BidBench claim-trace metric usable against a real governed
workflow run without exporting customer project data or allowing a hand-made
candidate to hide an incorrect claim/evidence topology.

## Delivered

- Added a read-only offline capture adapter that binds one reviewed private
  manifest to one succeeded draft/redraft `ExecutionRun`, generated
  `SectionVersion`, and succeeded workflow `RuntimeRun` bridge.
- Required exact mapping coverage for current project requirements, support
  evidence, Claim evidence, and every Claim created by the execution run.
- Preserved structural errors as opaque unmatched candidate references so
  BidBench scores them negatively instead of silently dropping them.
- Rejects a reviewed manifest that attempts to reuse any durable runtime
  identifier as an exported candidate identifier.
- Added an explicit-confirmation CLI that writes only below `output/`; it has
  no API route, Worker task, or browser entry point.
- Added regression coverage for redaction, unmatched evidence, failed runtime
  provenance, incomplete mapping, and a same-run Claim that points at a wrong
  section version.

## Privacy Boundary

The private manifest is an operator-controlled input and must remain outside
the repository, candidate, and report. Generated candidates contain no project,
organization, user, execution, runtime, section, requirement, evidence, or
Claim IDs; no claim/evidence/source text; no locators; no filenames; no prompts;
and no provider payloads.

## Verification

- CLI help and explicit acknowledgement boundary verified locally.
- Related isolated PostgreSQL regression: `114 passed`.
- Targeted Ruff and `git diff --check` passed.

## Follow-up

Collect a reviewed synthetic/public controlled capture, compare it with hidden
regression evidence, then propose a claim-trace threshold as policy. A
version-level export gate remains a separate design and migration effort.
