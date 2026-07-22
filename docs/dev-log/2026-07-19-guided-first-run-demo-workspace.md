# Guided First-Run Demo Workspace

## Why this slice

The product refoundation requires a guided first run and sample dataset, while
the commercial launch gap list identifies external-pilot onboarding as open.
The previous three-step onboarding card only described the workflow; it did not
let a user inspect BidPilot's requirement, evidence, readiness, and audit
surfaces without first sourcing a tender package and configuring a model.

## Delivered behavior

- `POST /projects/demo` creates a user-owned, active-organization demo
  workspace or returns that user's existing one.
- The workspace contains three authenticated built-in markdown sources, parsed
  source records, sparse-search-ready chunks, six Requirement Ledger entries,
  three evidence records, evidence links, default deliverable sections, and a
  `project.demo_seeded` audit event.
- It uses no model/provider call, Worker job, object-storage upload, or AI
  usage reservation. It does consume one normal project entitlement when it
  is created.
- Built-in documents retain a `builtin://bidpilot-demo/` marker and download
  through the normal authorized document endpoint.
- The dashboard and onboarding wizard now offer two explicit paths: use own
  documents or explore the demo workspace.
- The same operation is a registered `create_demo_workspace` Agent
  capability. It is a low-risk write, requires approval in the default
  `risky_only` mode, remains auditable, and has a user-facing tool label.

## Important constraints

- This is a transparent product tour, not a synthetic successful AI run.
  It creates no generated draft, SectionVersion, ExecutionRun, or readiness
  export.
- A real parse, retrieval, drafting, review, or export remains governed by
  normal provider, quota, policy, and approval controls.
- The endpoint must not become a way to bypass project quotas or create a
  shared cross-user sample project.

## Verification completed

- API project/demo, assistant policy, harness, project, E2E, and requirement
  coverage passed on the dedicated test database.
- Full API suite: `594 passed`.
- Full Worker suite: `113 passed`.
- Frontend unit suite: `25` test files and `92` tests passed.
- API and Worker Ruff checks, frontend TypeScript check, Alembic head, and the
  production frontend build passed.
- The API suite finishes in approximately 115 seconds locally. Its output was
  captured as passing even though the desktop terminal wrapper reached its
  two-minute command ceiling during post-command cleanup.
- The production-default Operator has a deliberately narrow provider-free
  fast path for `create_demo_workspace`: it bypasses provider resolution,
  model dispatch, and Assistant quota accounting, but still creates a durable
  `RuntimeRun` and requests approval in `risky_only` mode. Confirmation resumes
  the same deterministic Runtime run rather than being sent to the LangGraph
  operator adapter.
- Targeted Runtime, project, and harness coverage passed: `37 passed`.
  The Assistant panel's focused web suite passed: `22 passed`, including the
  post-create navigation regression.
- An authenticated local browser trace verified the empty dashboard, a
  no-provider Assistant request for "创建演示工作区", the user-facing approval
  card, approval completion, and the resulting demo workspace summary. A
  separate authenticated browser trace verified parsed sources, Requirement
  Ledger entries, evidence, and default sections.

## Remaining evidence

- A deployed-candidate trace remains separate from local test evidence. It
  must not use a production provider credential or be represented as a model
  execution when it only seeds the deterministic workspace.
