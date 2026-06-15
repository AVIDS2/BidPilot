# BidPilot Assistant Harness v1 Design

## Goal

Build a first real platform assistant for `BidPilot` that can do more than chat. It should understand user intent, execute safe platform actions through controlled tools, trigger existing LangGraph workflows when needed, and expose clear execution state in the UI.

This assistant is not a generic agent playground. It is a product-native execution assistant for the `BidPilot` platform.

## Why this exists

The current AI panel is useful as a chat surface, but it is still mostly a conversational wrapper around:

- prompt suggestions
- page navigation shortcuts
- SSE-based chat completions

It does not yet behave like a real platform agent. Users cannot reliably ask it to perform platform tasks such as:

- create a project
- find the right project
- open the right upload target
- trigger drafting for a section
- explain what it is doing while it works
- confirm risky operations before execution

This design closes that gap.

## Design Principles

### 1. Workflow-first core, assistant-enhanced UX

`BidPilot` remains a workflow product first. Durable business execution still belongs to the existing control plane plus LangGraph-based execution layer.

The assistant improves how users access and orchestrate those capabilities.

### 2. Harness and workflow are different layers

The assistant runtime is not the same thing as the long-running document workflow engine.

- `OpenAI Agents SDK` is used for assistant harness concerns
- `LangGraph` remains the engine for long-running, stateful document execution workflows

### 3. Tools over free-form platform mutation

The model must never be treated as if it can directly mutate the platform. It can only act through explicit, typed, auditable tools.

### 4. Explain execution without exposing raw chain-of-thought

The UI should show high-signal execution summaries:

- what the assistant understood
- what tool it is calling
- what data is missing
- why user confirmation is needed
- whether a workflow has started

It should not expose raw hidden reasoning.

### 5. Safe by default

The assistant should ask for confirmation before any action with non-obvious effect, data mutation, or external cost.

## Scope

### In scope for v1

- assistant runtime based on `OpenAI Agents SDK`
- typed tool registry for core platform actions
- intent routing between:
  - direct answer
  - platform tool execution
  - LangGraph workflow trigger
- session-scoped assistant history
- assistant execution event model for the frontend
- frontend assistant state machine and execution UI
- confirmation gate for risky actions
- audit-friendly event logging

### Out of scope for v1

- open-ended autonomous multi-step self-directed planning
- arbitrary code execution
- arbitrary file system mutation from the assistant
- generic MCP marketplace style tool ecosystem
- fully autonomous workflow retries without user visibility
- multi-agent debate or complex internal handoff trees

## Core Architecture

The system is split into two layers.

### Layer A: Assistant Harness

This layer is responsible for:

- understanding the user's request
- choosing whether to answer, ask for missing input, execute a direct tool, or trigger a workflow
- validating tool arguments
- enforcing confirmation and safety policies
- emitting structured execution events for the UI

Recommended implementation surface:

- backend Python service layer using `OpenAI Agents SDK`

### Layer B: Workflow Engine

This layer already exists and continues to own:

- RFP parsing
- knowledge retrieval
- drafting
- quality review
- HITL approval
- persistence
- resumable execution

Implementation surface:

- existing `LangGraph` graph under `services/worker/app/graph/`

### Relationship

The assistant harness may call the workflow layer as one tool among many.

Examples:

- "Create a new project called XX" -> direct tool action
- "Upload this RFP to my latest project" -> direct tool action plus UI bridge
- "Draft the executive summary for this project" -> trigger drafting workflow

This means:

- assistant != workflow
- assistant can trigger workflow
- workflow results are reported back through assistant execution events

## OpenAI Agents SDK Fit

`OpenAI Agents SDK` is used because it fits the harness layer well:

- tools
- sessions
- guardrails
- handoffs if needed later
- traceability
- structured model-mediated tool use

It is not being chosen to replace `LangGraph`. It is being chosen to wrap product actions safely.

## Assistant Modes

The assistant should classify each user input into one of four modes.

### 1. Answer

Pure informational response.

Examples:

- "What is the difference between draft and review?"
- "How do I use this page?"

### 2. Needs Input

The user intent is understood, but required parameters are missing.

Examples:

- "Create a project" with no project name
- "Draft a section" with no project or section

### 3. Tool Action

The request can be satisfied by one or more fast platform tools.

Examples:

- create project
- navigate to project
- list pending reviews
- open provider settings

### 4. Workflow Trigger

The request requires durable execution in the LangGraph layer.

Examples:

- draft section
- redraft with review feedback
- run a longer document-processing path

## Tool Registry

The assistant harness will expose a controlled set of typed tools.

### Phase 1 tools

- `search_projects`
  - input: `query?: str`, `status?: str`
  - output: list of matching projects

- `create_project`
  - input: `name: str`, `scenario_package?: str`
  - output: created project

- `get_project_summary`
  - input: `project_id: str`
  - output: project metadata and high-level status

- `list_project_bundles`
  - input: `project_id: str`
  - output: bundle list

- `prepare_upload_target`
  - input: `project_id: str`, `bundle_id?: str`
  - output: bundle target info for the UI uploader

- `list_sections`
  - input: `project_id: str`
  - output: known deliverable sections

- `start_draft_section`
  - input: `project_id: str`, `section_key: str`, `provider_config_id?: str`
  - output: run identifier
  - implementation: triggers existing drafting API / workflow path

- `start_redraft_section`
  - input: `project_id: str`, `section_key: str`, `review_feedback: str`, `provider_config_id?: str`
  - output: run identifier

- `list_pending_reviews`
  - input: `project_id?: str`
  - output: pending review targets

- `open_page`
  - input: `route: str`
  - output: route acknowledgement
  - frontend effect: navigates platform UI

- `get_runtime_status`
  - input: none or `project_id?: str`
  - output: summary of runs / queues / recent execution state

### Future tools

- `resume_human_approval`
- `export_deliverable`
- `search_knowledge`
- `assign_team_member`

## Safety and Confirmation

The assistant must not execute every tool immediately.

### No-confirmation actions

Safe, reversible, or read-only actions:

- answer question
- search projects
- get project summary
- list bundles
- list sections
- open page
- list pending reviews

### Confirmation-required actions

Any action that creates, mutates, triggers cost, or launches longer execution:

- create project
- trigger draft
- trigger redraft
- export deliverable
- submit review decision

### Missing-input policy

If required tool inputs are missing:

- do not guess silently
- ask for the smallest missing set
- keep the pending action context in the session

## Assistant Session Model

The current chat history system already supports:

- conversations
- messages

v1 extends this with assistant execution context in memory and optionally in durable storage later.

### Session state fields

- current conversation id
- current page
- current project id if available
- pending action intent
- pending confirmation payload
- last tool result summary
- currently running workflow run id if any

## Frontend UX

The assistant panel should evolve from chat-only UI into an execution-aware assistant surface.

### Required UX elements

#### 1. Status state machine

Frontend assistant states:

- `idle`
- `thinking`
- `needs_input`
- `needs_confirmation`
- `executing_tool`
- `running_workflow`
- `completed`
- `failed`

#### 2. Execution summary bar

A compact status line near the header:

- "Understanding request"
- "Waiting for your confirmation"
- "Creating project"
- "Starting draft workflow"
- "Done"

#### 3. Tool execution cards

Each direct action should render as a visible execution card:

- tool name
- short argument summary
- result summary
- success / failure state

#### 4. Confirmation cards

Before mutation:

- show a confirmation card
- show exactly what will happen
- let user confirm or cancel

#### 5. Workflow progress cards

When a LangGraph workflow is triggered:

- show run id
- show current workflow phase
- show that long-running execution has moved to the workflow engine

#### 6. Conversation history

Already added in the current UI. It should remain and become one pillar of the assistant UX.

#### 7. Rich rendering

Assistant messages must support:

- markdown
- code blocks
- math rendering
- execution cards

## Event Model Between Backend and Frontend

The assistant should not return only plain chat text. It should emit structured events.

### Proposed assistant event types

- `assistant.message`
- `assistant.intent_detected`
- `assistant.missing_input`
- `assistant.confirmation_requested`
- `assistant.tool_started`
- `assistant.tool_succeeded`
- `assistant.tool_failed`
- `assistant.workflow_started`
- `assistant.workflow_update`
- `assistant.workflow_completed`
- `assistant.workflow_failed`

The frontend uses these events to render status, cards, and progressive execution UX.

## Backend Execution Flow

### Direct tool path

1. User sends message
2. Assistant harness classifies intent
3. If inputs missing -> return `needs_input`
4. If confirmation required -> return confirmation request
5. On confirmation -> execute tool
6. Return tool result + optional assistant explanation

### Workflow path

1. User sends message
2. Assistant harness classifies intent as workflow trigger
3. Validate / resolve project and section
4. Ask for confirmation if needed
5. Trigger drafting API / workflow entrypoint
6. Return workflow-start event
7. Frontend subscribes to existing run progress stream

## Relationship to Existing Code

### Existing pieces we should reuse

- chat conversation storage
- SSE streaming path
- existing API client
- existing drafting endpoints
- existing execution run streaming
- existing project / document / review APIs

### Existing gaps to fill

- assistant-specific tool registry
- intent-to-tool mapping
- confirmation state
- execution event payloads beyond plain text chunks
- frontend execution card rendering

## Suggested Initial File Layout

### Backend

- `services/api/app/assistant/`
  - `__init__.py`
  - `schemas.py`
  - `runtime.py`
  - `tools.py`
  - `guardrails.py`
  - `service.py`

### Frontend

- `apps/web/src/components/ai-assistant/`
  - evolve `AIAssistantPanel.tsx`
  - add `assistant-execution-card.tsx`
  - add `assistant-confirmation-card.tsx`
  - add `assistant-workflow-card.tsx`

## Rollout Plan

### v1

- direct actions: create project, navigate, list reviews, trigger draft
- confirmation support
- execution cards
- workflow trigger bridge

### v1.1

- better project/section resolution
- richer run progress inside assistant
- action retry and resume affordances

### v2

- multi-step tool sequences
- smarter stateful follow-up resolution
- organization / team scoped actions

## Non-goals for v1 Implementation

- self-directed autonomous loops
- open-ended agent planning over arbitrary tools
- replacing core LangGraph workflow
- building a general-purpose enterprise agent platform

## Success Criteria

The design is successful when:

- a user can ask for a project to be created and the assistant really creates it
- a user can ask to draft a section and the assistant really triggers the workflow
- the assistant clearly shows what it is doing
- mutation actions require confirmation
- all actions remain bounded by explicit tools
- the assistant feels like a platform operator, not only a chat box

## Recommendation

Implement `BidPilot Assistant Harness v1` as:

- `OpenAI Agents SDK` for the assistant harness layer
- existing `LangGraph` workflows for long-running business execution
- a frontend assistant execution UX that exposes status, tools, confirmation, and workflow state

This keeps the architecture aligned with the product's real shape:

- workflow-first core
- agent-enhanced user experience
