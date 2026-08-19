# Progress Log

## 2026-08-19

- Formal-release candidate uses Pi for all new Assistant turns; lexical routing
  and the retired Python Harness are not production fallbacks.
- Golden bid-response path passed 10/10 with company-evidence separation,
  requirement extraction, evidence mapping, human review, immutable redraft,
  DOCX export, retry recovery, and traceable material manifests.
- Live Chromium validation passed the user journey from registration through
  project creation, ingestion, Assistant status inspection, drafting, approval,
  and download.
- Release rehearsal passed with API `822 passed / 60 skipped`, Worker `194
  passed`, Web `154 passed`, Pi sidecar `12 passed`, mobile Chromium `5 passed`,
  and the local load smoke at zero failures.
- Long-section drafting completion budget increased from 4,096 to 16,000 after a
  real provider truncation was reproduced; regression tests cover the contract.
- Next handoff entry: use the production deployment record and post-release smoke
  evidence as the source of truth before beginning new product work.
- The first production promotion attempt correctly failed readiness because the
  legacy outer Compose topology did not contain `pi-agent`. The deploy helper is
  now fail-closed for Pi: it requires the complete versioned production Compose
  and the dedicated internal bridge secret instead of partially replacing API,
  Worker, and Web against an incomplete topology.
