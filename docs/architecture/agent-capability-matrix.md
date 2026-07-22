# Governed Agent Capability Matrix

## Purpose

BidPilot's Assistant is an execution interface for the bid-response lifecycle,
not a generic chat widget and not an unrestricted system administrator. It may
plan and request product actions, but PostgreSQL remains the business source of
truth and every mutation crosses the Runtime policy boundary.

The goal is that a proposal manager can work from a conversation while a
reviewer, administrator, or auditor can still determine what changed, who
authorized it, and which source materials support the result.

## Plane Boundary

| Plane | Owns | Must not be replaced by the Assistant |
| --- | --- | --- |
| Assistant operator | Interpreting a user request, choosing a registered capability, reporting bounded progress | Business truth, authorization decisions, or a hidden model-only approval state |
| Product control plane | Projects, bundles, documents, requirements, evidence, deliverables, reviews, exports, audit records | None |
| Workflow execution plane | Parsing, indexing, retrieval, drafting, validation, and retryable long-running work | User-facing authorization or final business state without persistence |
| Human security plane | Team membership, organization security, billing, provider-key administration, destructive confirmation | None |

The LangGraph Operator is deliberately bounded to registered capabilities. A
model cannot invent a tool, execute arbitrary code, read a local filesystem,
or bypass `execute_capability`. LangGraph checkpoint state is resumable
execution context only; it is never the record of a project, approval, review,
or export.

## Bid Lifecycle Coverage

| Lifecycle stage | User outcome | Operator capability / route | Durable result | Default governance |
| --- | --- | --- | --- | --- |
| Create workspace | A bid project with the BidPilot template is created | `create_project` | `Project`, owner `ProjectMember`, standard deliverable and sections, audit event | Confirmation in `risky_only`; runtime action is idempotent |
| Add source material | Files become governed project evidence | `POST /assistant/attachments` then `attach_uploaded_documents` | Private `AssistantAttachment` staging record, copied `SourceDocument`, bundle, ingest job, usage/audit record | Upload requires authenticated ownership; project handoff is confirmation-gated and quota-checked |
| Inspect context | See projects, files, sections, requirements, evidence, versions, and run state | Read capabilities such as `search_projects`, `list_documents`, `list_requirements`, `list_evidence`, `get_runtime_status` | No mutation; only access-filtered read models | Project membership is enforced before every scoped read |
| Assess compliance | Identify readiness score, missing evidence, mandatory gaps, and source locations | `get_readiness_summary`, `list_readiness_gaps`, `open_requirement_source` | Requirement Ledger and evidence links remain authoritative | Read-only; source locators are returned through a bounded public result |
| Draft response | Start a section draft or redraft | `start_draft_section`, `start_redraft_section` | `ExecutionRun`, bridge `RuntimeRun`, ordered runtime events, versioned section output and evidence | Costing action; confirmation plus workflow quota before queueing |
| Review decision | Approve or return a section with a human decision | `submit_review_decision` | Review decision/thread, section state, audit history | Requires a reviewer-capable project member and confirmation in `risky_only` |
| Create readiness pack | Produce structured project readiness artifacts | `generate_readiness_pack` | Versioned `ReadinessPack`, DOCX/XLSX artifacts, audit evidence | Confirmation in `risky_only`; authenticated download only |
| Export delivery | Render an approved deliverable | `export_deliverable` | Approved-section export artifact and audit event | Costing action; approved content only; authenticated download only |
| Clean up | Remove a project from active work | `delete_project` | Soft-deleted project state and audit evidence | Destructive; always requires typed project-name confirmation |

## Public Result Contract

The UI renders a user-facing summary, localized capability label, status, and
permitted action. It must never render raw tool call dumps, database keys,
storage keys, provider credentials, prompt text, or worker exception traces.

For generated artifacts, the runtime may expose only an allow-listed relative
download path. The web client fetches it with the user's bearer token and
streams a Blob download; it never places a bearer token in a URL and never
shows the internal object-storage key.

## Attachment Data Lifecycle

1. Browser uploads an attachment to authenticated private staging.
2. The API records ownership, checksum, metadata, bounded extraction status,
   and a 24-hour expiry in `AssistantAttachment`.
3. The planner sees metadata and opaque attachment IDs. The browser cannot
   choose the text that enters the planner.
4. An approved ingestion capability copies raw bytes into a project-scoped
   `SourceDocument`, queues ordinary ingestion, records usage and audit data,
   and deletes the staging object.
5. Celery Beat expires unused staging records and retries failed cleanup.

This separation prevents a conversational upload from silently becoming shared
project evidence, while still supporting a natural request such as “create a
project and process these files.”

## Approval and Access Rules

- `request_approval`: every mutation pauses for confirmation.
- `risky_only`: reads run directly; writes, provider-costing work, and exports
  require confirmation.
- `full_access`: low-risk actions can proceed without the interaction pause,
  but authorization, quotas, audit records, and typed confirmation for
  destructive deletion remain mandatory.
- `custom`: reserved for a future organization policy profile; it must map to
  explicit server-side policy, never browser-only switches.

Approval does not grant a permission. The target project, deliverable, section,
run, attachment, and readiness pack are checked in the domain service using
the acting user's organization and project role.

## Intentionally Human-Only Operations

The Assistant should navigate users to these surfaces but must not receive an
unbounded tool for them:

- organization ownership and membership changes;
- billing, subscription, invoices, and payment methods;
- provider keys, platform keys, and model-provider trust policy;
- security settings, authentication policy, data retention policy, or audit
  exports that cross project boundaries;
- production deployment, infrastructure, filesystem, shell, or network access.

This is the distinction between a product operator and a coding agent. It keeps
BidPilot useful in an enterprise setting without turning a chat request into an
unreviewable administrative control path.

## Required Evidence Before a Release Claim

The capability matrix is implementation coverage, not proof that an AI model
produces high-quality bid content. A release/pilot claim still requires:

1. An authenticated deployed end-to-end run: create, ingest, parse, extract,
   draft, review, readiness pack, and export.
2. A frozen BidBench/evaluation report covering requirement recall, evidence
   grounding, mandatory-gap handling, and output quality.
3. A failure-path rehearsal for provider failure, queue retry, approval expiry,
   staging cleanup, and download authorization.
4. A non-developer acceptance pass using the demo guide and a realistic source
   bundle.

## Implementation Anchors

- Capability metadata and public-result redaction: `services/api/app/runtime/registry.py`
- Authorization, policy, idempotency, approval, and events: `services/api/app/runtime/service.py`
- Bounded LangGraph Operator: `services/api/app/runtime/operator_graph.py`
- SSE/runtime replay adapter: `services/api/app/runtime/operator_adapter.py`
- Product tools: `services/api/app/assistant/tools.py`
- Durable attachment staging: `services/api/app/assistant/attachments.py`
- User-facing activity and downloads: `apps/web/src/components/ai-assistant/assistant-activity-timeline.tsx`
