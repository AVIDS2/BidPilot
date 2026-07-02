# BidPilot Agent-First Platform Operator v1 Design

## Goal

Upgrade the BidPilot assistant from a chat companion into a platform operator that can safely control the product on behalf of the user.

The target experience is similar to Codex or Claude Code:

- the user describes an outcome
- the agent creates a short execution plan
- the agent executes platform actions through controlled tools
- risky actions pause for approval
- progress is streamed as first-class execution state
- every action is auditable and bounded by permissions

This is not a generic autonomous agent playground. It is a BidPilot-native operator for bid projects, documents, workflows, reviews, and delivery.

## Product Positioning

BidPilot should become agent-first, but not agent-only internally.

The user may use the agent as the primary entry point. The platform still keeps explicit project pages, workflow pages, settings pages, billing pages, and admin surfaces for inspection and manual correction.

The agent is the operator. PostgreSQL remains the business source of truth. LangGraph remains the stateful execution engine. The frontend remains the user-visible command center.

## Design Principles

### 1. Agent can operate, not merely suggest

The assistant should be able to perform platform actions:

- create and update projects
- import attachments into project bundles
- create deliverables and default sections
- start drafting workflows
- retry failed runs
- navigate the UI
- summarize project state
- prepare exports
- delete or archive resources when explicitly approved

It must not say "you can go do this" when a safe tool exists.

### 2. Tools are product capabilities

Tools are not raw database helpers. Each tool wraps an existing platform service command or query.

This keeps business rules, quotas, organization isolation, audit logging, and provider selection centralized.

### 3. Permissions are explicit modes

The user should be able to choose an approval mode similar to Codex:

- request approval
- approve detected risky actions only
- full access
- custom policy

The mode changes what the agent may do without pausing, but never bypasses server-side authorization.

### 4. Dangerous actions require hard gates

Deletion, destructive overwrite, billing-affecting operations, provider-key changes, and high-cost workflow starts must not rely on prompting alone.

They require a backend-enforced approval gate, implemented with LangGraph interrupt/resume or an equivalent durable pending-action record.

### 5. Sandbox first

The agent should run inside a BidPilot action sandbox. The sandbox defines:

- which tools are available
- which resources can be touched
- whether external network actions are allowed
- which actions require approval
- which actions are forbidden
- whether the action is dry-run only

The sandbox is product-level, not OS-level. BidPilot is a web application, so the sandbox governs platform APIs, not local filesystem access.

### 6. Observable execution over hidden reasoning

The UI should show:

- plan
- actions
- approvals
- tool progress
- workflow progress
- final result

It must not expose hidden chain-of-thought. It should expose concise operational reasoning, e.g. "I need the project name before I can create it."

## LangGraph Role

LangGraph is appropriate for the agent operator layer because it provides:

- durable loops
- tool calling
- stateful conversations
- checkpointing
- human-in-the-loop interrupts
- resume with the same thread id
- multi-step execution patterns

LangGraph does not replace BidPilot's business services. It orchestrates them.

### Required LangGraph capabilities

The operator must use:

- checkpointer for persistent conversation and pending execution state
- thread id mapped to `conversation_id`
- interrupt/resume for approval gates
- tool call streaming for frontend execution display
- loop limits to avoid runaway tool calls

### Production persistence

`InMemorySaver` is acceptable only for local development and tests.

Production must use Postgres-backed checkpointing or an equivalent durable checkpointer. If PostgresSaver setup fails in production, the API should fail closed or explicitly disable operator execution rather than silently falling back to memory.

## System Layers

### Layer 1: Frontend Operator Surface

The frontend provides the command surface:

- assistant side panel
- optional full-page agent workbench
- approval mode selector
- input composer with attachments
- execution timeline
- workflow visualization bridge
- action review and confirmation cards

The frontend does not enforce security. It visualizes backend state and sends approval decisions.

### Layer 2: Agent Loop Engine

This is the LangGraph agent loop.

Responsibilities:

- understand user intent
- plan short action sequences
- call allowed tools
- pause for approval when required
- resume after approval
- produce final answer

The loop should have a max iteration budget per turn.

### Layer 3: Action Policy and Sandbox

This is the BidPilot-specific harness around tools.

Responsibilities:

- classify tools by risk
- apply the current approval mode
- enforce resource scope
- validate arguments
- create approval payloads
- block forbidden actions
- audit all actions

This layer is required even if the model prompt says it should ask for approval.

### Layer 4: Platform Tool Registry

Tools wrap business services:

- project service
- document service
- bundle service
- deliverable service
- drafting service
- execution service
- provider config service
- billing and quota service
- navigation pseudo-tool

Every tool has:

- stable name
- user-facing label
- description
- input schema
- output schema
- risk level
- required permissions
- audit event type

### Layer 5: Existing Workflow Engine

Long-running bid workflows remain in existing worker/LangGraph execution:

- parsing
- chunking
- embedding
- retrieval
- drafting
- review
- export preparation

The operator starts, monitors, and explains workflows. It does not inline all workflow internals into the chat loop.

## Approval Modes

### Request Approval

The safest mode.

The agent asks before:

- creating resources
- changing resources
- starting workflows
- exporting
- deleting
- using external provider credits
- sending notifications

Read-only and navigation tools may run directly.

### Approve Risky Actions Only

Balanced default for most logged-in users.

The agent may run low-risk mutations without approval, such as:

- create a draft-only deliverable shell
- create an upload bundle
- rename a conversation
- navigate to a page

It must ask before:

- deleting
- archiving
- overwriting generated content
- starting paid workflow runs
- changing provider configuration
- inviting team members
- exporting final delivery files

### Full Access

Power-user mode.

The agent may perform most actions without asking, but the backend still requires hard confirmation for:

- delete project
- delete account
- delete provider key
- billing plan changes
- irreversible data purge
- external send operations

This mode should show a visible warning badge.

### Custom Policy

Advanced mode.

The user or organization can configure a policy similar in spirit to a `config.toml`, but stored in the application database.

Example policy:

```toml
[approval]
default = "risky_only"
delete_project = "always"
start_paid_workflow = "always"
create_project = "auto"
rename_project = "auto"

[scope]
allowed_projects = ["current"]
allow_provider_changes = false
allow_billing_changes = false
```

The product may later expose import/export for this policy, but v1 stores it server-side.

## Risk Levels

### Read

No mutation and no external cost.

Examples:

- search projects
- get project summary
- list documents
- list sections
- list workflow runs
- semantic search

Default behavior: auto-run.

### Navigate

Only changes frontend route.

Examples:

- open project page
- open provider settings
- open workflow visualization

Default behavior: auto-run.

### Low-Risk Write

Creates or updates reversible metadata.

Examples:

- create project
- rename project
- create bundle
- create deliverable shell
- create default sections
- rename conversation

Default behavior: depends on approval mode.

### Costing or Long-Running

Starts AI, embedding, parsing, export, or worker jobs.

Examples:

- parse uploaded documents
- create embeddings
- draft section
- redraft section
- retry workflow
- export DOCX/PDF

Default behavior: approval required in request-approval and risky-only modes.

### Destructive

Deletes, archives, overwrites, or purges.

Examples:

- delete project
- delete bundle
- delete document
- delete provider configuration
- overwrite approved section
- revoke team access

Default behavior: hard approval required in all modes. For project deletion, the user must confirm the project name.

## Sandbox Model

### Session Sandbox

Applies to a single conversation.

Contains:

- current project id
- selected provider config id
- reasoning effort
- approval mode
- uploaded attachment ids
- allowed resource ids
- pending approvals

### Project Sandbox

Applies when the agent operates inside a project.

Rules:

- tool calls default to the current project
- cross-project actions require explicit mention or confirmation
- attachments uploaded in this context can be imported into the current project

### Organization Sandbox

Applies to organization-wide administration.

Rules:

- team, billing, provider, and invitation tools require org-level permissions
- free users may be blocked by quota policy
- admin-only tools are hidden from non-admin users

### Dry-Run Sandbox

The agent can produce a plan and simulated effects without executing.

Example:

```text
先别执行，模拟一下如果我上传这批资料，你会怎么创建项目和章节。
```

The output should list actions, expected resources, and required approvals.

## Tool Coverage for v1

### Project Tools

- `search_projects`
- `create_project`
- `rename_project`
- `archive_project`
- `delete_project`
- `get_project_summary`
- `open_project`

### Bundle and Document Tools

- `create_bundle`
- `list_project_bundles`
- `import_uploaded_attachment_to_bundle`
- `list_documents`
- `reingest_bundle`
- `get_document_text_summary`

### Deliverable Tools

- `create_deliverable`
- `create_default_sections`
- `list_deliverables`
- `list_sections`
- `rename_section`
- `get_section_versions`

### Workflow Tools

- `start_draft_section`
- `start_redraft_section`
- `get_runtime_status`
- `retry_run`
- `open_workflow_visualization`

### Knowledge Tools

- `semantic_search`
- `list_requirements`
- `list_evidence`
- `summarize_uploaded_attachments`

### Export Tools

- `prepare_export`
- `export_deliverable`

### Navigation Tools

- `open_page`
- `open_settings_providers`
- `open_pricing`
- `open_docs`

## Canonical User Flows

### Flow 1: Create a Project from Attachments

User:

```text
我上传了这些资料，帮我创建一个智慧社区投标项目并整理好。
```

Agent:

1. reads attachment metadata and extracted text
2. proposes project name
3. proposes bundle grouping
4. asks for approval
5. creates project
6. creates bundles
7. imports attachments
8. creates default deliverable and sections
9. opens project page

### Flow 2: Start Drafting

User:

```text
帮我起草技术方案。
```

Agent:

1. resolves current project
2. resolves section key
3. checks provider and quota
4. asks for approval if needed
5. starts drafting workflow
6. opens workflow visualization or shows inline workflow status

### Flow 3: Delete Project

User:

```text
把 test 项目删了。
```

Agent:

1. searches matching projects
2. if multiple matches, asks the user to choose
3. shows destructive warning
4. requires the user to confirm the exact project name
5. deletes only after confirmation
6. audits the deletion

### Flow 4: Agent as Primary Entry

User:

```text
我要完成一个智慧社区平台投标，从资料整理到技术方案起草，你来。
```

Agent:

1. asks for files if none are present
2. creates a plan
3. executes approved setup steps
4. starts the first workflow
5. shows next recommended action

## Frontend UX Requirements

### Approval Mode Selector

Add a selector near the composer, inspired by Codex:

- 请求批准
- 替我审批
- 完全访问
- 自定义

English labels:

- Request approval
- Approve risky actions
- Full access
- Custom

The selector should show a small risk badge, not an alarming modal.

### Execution Timeline

The first assistant output should be an execution timeline when tools are involved.

Example:

```text
已处理 4 项操作
```

Expandable details:

- 已创建项目「智慧社区投标」
- 已上传 3 个文件
- 已创建 11 个章节
- 已启动技术方案起草

Raw tool JSON must not be shown by default.

### Approval Cards

Approval cards should show:

- action name
- affected resource
- consequences
- whether it is reversible
- approve / cancel buttons

Destructive actions require typed confirmation.

### Full-Page Agent Workbench

The side panel is too narrow for complex tasks.

Add an optional full-page route later:

- `/agent`
- left: conversations and projects
- center: chat and execution timeline
- right: workflow graph, artifacts, approvals, files

The side panel remains for quick operations.

## Backend API Requirements

### Stream Endpoint

`POST /assistant/stream` continues to be the main endpoint.

It must support:

- new user message
- approval resume
- selected approval mode
- selected provider config
- reasoning effort
- attachment ids

### Approval Resume

Approval decisions should include:

- conversation id
- approval id or interrupt id
- decision
- optional edited arguments
- typed confirmation string when required

### Event Types

Required SSE events:

- `assistant.start`
- `assistant.plan_started`
- `assistant.plan_updated`
- `assistant.approval_required`
- `assistant.approval_resolved`
- `assistant.tool_started`
- `assistant.tool_succeeded`
- `assistant.tool_failed`
- `assistant.workflow_started`
- `assistant.workflow_updated`
- `assistant.message`
- `assistant.end`

## Data Model Additions

### Assistant Policy

Stores user or organization policy.

Fields:

- `id`
- `scope_type`: user or org
- `scope_id`
- `approval_mode`
- `policy_json`
- `created_at`
- `updated_at`

### Assistant Action Audit

Stores action attempts and outcomes.

Fields:

- `id`
- `conversation_id`
- `user_id`
- `org_id`
- `tool_name`
- `risk_level`
- `arguments_json`
- `status`
- `result_summary`
- `created_at`
- `completed_at`

### Assistant Approval

Stores pending approvals if LangGraph interrupt payloads need a product-side mirror.

Fields:

- `id`
- `conversation_id`
- `thread_id`
- `tool_name`
- `risk_level`
- `payload_json`
- `status`
- `expires_at`
- `resolved_at`

## Implementation Strategy

### Phase 1: Policy and Tool Coverage

Implement:

- tool metadata registry
- risk levels
- approval mode enum
- missing LangGraph tools, including delete project
- user-facing tool labels
- audit records

### Phase 2: Hard Approval Gate

Implement:

- interrupt/resume for high-risk tools
- durable checkpointer in production
- typed confirmation for destructive tools
- frontend approval cards

### Phase 3: Attachment-to-Project Automation

Implement:

- import uploaded assistant attachments into project bundles
- create project from attachments
- create default deliverable and sections
- demo project one-command flow

### Phase 4: Agent Workbench

Implement:

- full-page `/agent`
- execution timeline
- files/artifacts rail
- workflow graph rail
- approval queue

## Safety Requirements

- Never expose provider keys to the frontend.
- Never log decrypted provider keys.
- Never show raw tool JSON by default.
- Never let the model bypass org isolation.
- Never silently downgrade production checkpointing to memory.
- Destructive tools require hard approval even in full-access mode.
- External provider calls must respect quota and rate limits.
- Every mutation must be auditable.

## Non-Goals for v1

- arbitrary code execution
- OS-level shell sandbox
- arbitrary internet browsing by the platform agent
- unrestricted MCP tool marketplace
- autonomous billing changes
- autonomous provider key creation or deletion without approval
- background self-starting agent tasks without user initiation

## Success Criteria

v1 succeeds when:

- a user can upload files and ask the agent to create a project from them
- the agent can create bundles, import documents, create deliverables, and create sections
- the agent can start a drafting workflow and show progress
- the agent can delete a project only after hard confirmation
- approval mode affects low-risk behavior but not destructive safety
- production agent state survives service restart
- UI shows action summaries instead of raw tool JSON
- the agent can realistically serve as the primary entry point for a new user

