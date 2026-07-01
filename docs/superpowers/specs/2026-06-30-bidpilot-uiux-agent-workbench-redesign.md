# BidPilot UIUX and Agent Workbench Redesign

## Status

Draft for implementation.

## Product Read

BidPilot is an enterprise bid-execution workbench, not a generic document chatbot and not a marketing demo. The interface should feel like a serious B2B operating system for proposal teams: calm, precise, traceable, and agent-aware. The design target is closer to Linear, Claude Desktop, Codex, Raycast, and mature enterprise SaaS than to colorful AI landing pages.

The redesign must remove "AI-generated UI" tells: random blue or lime fills, decorative gradients, colorful left borders, noisy cards, raw tool traces, oversized generic buttons, and page-to-page visual discontinuity.

## Goals

- Establish a restrained visual system for all platform pages.
- Make the assistant feel like a real agent cockpit, not a chat demo.
- Add a dedicated agent workspace for complex tasks while keeping the floating panel lightweight.
- Upgrade workflow visualization into a live execution graph with clear node states.
- Keep all changes compatible with the current React, Vite, Tailwind v4, shadcn/ui, React Flow, and existing FastAPI streaming APIs.

## Non-Goals

- Do not replace the whole frontend framework.
- Do not introduce a second design system such as Fluent, Carbon, or Material in this phase.
- Do not rebuild all pages at once.
- Do not optimize for flashy Awwwards marketing aesthetics.
- Do not expose raw tool payloads, internal IDs, provider secrets, or debug traces in user-facing UI.

## Current Problems

### Theme and Tokens

`apps/web/src/index.css` currently defines a light theme with bright sky-blue tokens and a dark theme with lime-green primary tokens. This creates a cross-theme identity split. Many downstream components inherit these primary colors for buttons, selected states, progress, badges, and agent activity.

The global CSS also contains temporary comments such as "Teacher's dark style" and theme-specific one-off language. These are signs that the token system is not yet productized.

### Platform Pages

Dashboard, project list, project detail, and provider settings use several visually unrelated patterns:

- dashboard stats use blue, amber, violet, and emerald icon chips
- project guide cards use lime borders and gradients
- project detail workflow banner uses lime-gradient status pills
- provider settings uses colorful provider cards that feel like a plugin marketplace
- many primary actions rely on direct primary fill instead of a layered action hierarchy
- tabs are horizontally crowded and do not clearly separate work phases from governance/ops surfaces

### Assistant Panel

The assistant side panel is now functionally closer to the desired behavior after the turn-buffer fix, but it is still cramped for complex agent tasks. History, attachments, tool activity, markdown output, and confirmations all compete in a narrow drawer.

The side panel should remain useful for quick interactions. It should not be the only place for multi-step agent work.

### Agent and Workflow Views

`AgentTab` is currently a run selector plus `AgentProgress`. It is useful for debugging but not a product-level agent workspace.

`WorkflowCanvas` already uses React Flow, which is the right base, but the graph is a fixed long chain. Running nodes use primary glow, completed nodes use green, and the overall visual language still reads as a prototype. The graph needs a stronger state model and a more compact layout.

## Design Direction

### Visual Language

Use a "quiet operations cockpit" direction:

- neutral surfaces first
- one restrained brand accent
- semantic status colors only where status matters
- fewer cards, more structured sections and separators
- typography and spacing carry hierarchy more than color
- motion only for state transitions and live execution

Recommended dials:

- Design variance: 5/10
- Motion intensity: 4/10
- Visual density: 7/10

This is a dense product workbench. It should not become airy marketing UI.

### Token Strategy

Replace the split blue/lime identity with one stable token family.

Recommended base:

- background: near-neutral slate/graphite in dark mode, neutral off-white in light mode
- foreground: high-contrast neutral
- primary: restrained bid-agent accent, preferably a slightly desaturated blue-green or cyan-blue
- accent: same hue family as primary, lower chroma
- success/warning/destructive/info: semantic only, never decorative

Rules:

- Primary is for the single most important action or active route only.
- Status chips do not use primary unless status is "active agent task".
- Avoid gradients on operational cards. Gradients are allowed only in empty states or brand moments.
- Avoid colored left borders unless they encode severity or active navigation.
- Button variants must be meaningful: primary, secondary, outline, ghost, destructive.

### Shape, Shadow, and Density

- Use one radius scale: small controls 8px, cards/panels 14-18px, composer/assistant input 20-24px.
- Replace generic large shadows with subtle elevation tokens.
- Use separators and grouped rows instead of cards for dense operational data.
- Large dashboard cards should be reserved for summary metrics, not every content block.

## Assistant Experience

### Side Panel Role

The floating assistant panel should support:

- quick question
- quick navigation
- quick project search
- small confirmations
- upload one or two attachments
- lightweight status trace

It should not be the primary surface for long-running multi-step work.

### Dedicated Agent Page

Add a dedicated `/agent` route and optionally a project-scoped `/projects/:id/agent` route. The project detail tab can link into the project-scoped agent workspace.

The dedicated agent page should include:

- conversation column
- execution timeline column
- workflow graph/inspector column
- attachments and context drawer
- run history
- approval and confirmation rail

Desktop layout:

- left: conversation and composer
- center/right: live execution graph and timeline
- collapsible right rail: context, attachments, evidence, selected tool/node detail

Mobile layout:

- tabs: Chat, Activity, Workflow, Context
- composer pinned bottom

### Agent Turn Rendering

Each assistant turn must follow this order:

1. activity prelude appears first
2. tool/workflow rows update live
3. activity prelude collapses after terminal state
4. final assistant content appears after execution finishes

For direct answers without tools, text can stream immediately.

For turns with tools, assistant content is buffered until all running/pending activities for that turn are terminal. This is already started in `apps/web/src/lib/ai-assistant-store.tsx` and should become the formal contract.

### Activity Prelude

The collapsed activity prelude should look like:

- "已搜索 1 个项目"
- "已读取项目概览、资料包和章节"
- "正在生成章节草稿"
- "已运行 4 项操作"

Expanded details should show user-facing labels only:

- 搜索项目
- 读取项目概览
- 查看资料包
- 查看章节
- 启动章节起草

Never show:

- raw JSON
- `tool_call_id`
- function names as primary labels
- provider internals
- full UUIDs unless explicitly opened in an advanced debug view

### Attachments

Attachment UI should match modern AI assistant patterns:

- selected attachments appear as cards above the composer
- sent attachments appear outside the user bubble, aligned with the message
- image attachments show thumbnails
- file attachments show type, name, size, and extraction status
- backend extraction status is summarized as "已读取 / 暂不支持 / 读取失败", not raw fields

## Workflow Visualization

### React Flow Remains the Base

Keep `@xyflow/react` and evolve `WorkflowCanvas`. It is already installed and suitable.

### Node Model

Every workflow node should map to:

- id
- label
- role
- status: pending, queued, running, waiting_approval, completed, failed, skipped
- started_at
- completed_at
- summary
- evidence_count
- output_refs
- error

### Visual States

Pending:

- neutral border
- subdued label
- no glow

Queued:

- subtle dotted ring

Running:

- breathing pulse around the node
- animated edge into the node
- small live indicator

Waiting approval:

- amber semantic state
- explicit human handoff icon

Completed:

- neutral completed state with check marker
- avoid strong green fill

Failed:

- red semantic state
- error detail available in inspector

### Layout

Replace the current long horizontal chain with a grouped DAG:

- Intake: parse, normalize, requirement extraction
- Retrieval: search, evidence, context pack
- Drafting: plan, draft, revise
- Review: quality review, human approval
- Persist/export: save, audit, export

On smaller screens, use vertical stack mode.

### Inspector

Clicking a node opens an inspector panel:

- node summary
- inputs
- outputs
- evidence links
- duration
- model/tool used, if safe to show
- retry action if available

Do not overload node cards with all details.

## Page-Level Redesign Plan

### Phase 1: Design Tokens and Assistant/Agent Foundation

Files:

- `apps/web/src/index.css`
- `apps/web/src/lib/ai-assistant-store.tsx`
- `apps/web/src/components/ai-assistant/*`
- `apps/web/src/components/agent-progress.tsx`
- `apps/web/src/components/workflow-canvas.tsx`
- `apps/web/src/features/projects/tabs/agent-tab.tsx`

Deliverables:

- token cleanup for primary/accent/status
- assistant turn contract finalized
- activity prelude polish
- attachment cards polished
- workflow node state system refined
- project agent tab becomes a meaningful launch point to the dedicated workspace

Acceptance:

- no raw tool labels in normal assistant UI
- activity prelude always appears before tool-backed answer content
- assistant panel remains usable at 480px width
- workflow graph visually distinguishes running/completed/failed/waiting approval

### Phase 2: Dedicated Agent Workspace

Files:

- `apps/web/src/app.tsx`
- new `apps/web/src/features/agent/agent-workbench-page.tsx`
- new agent layout components under `apps/web/src/features/agent/components/`

Deliverables:

- `/agent` route
- optional `/projects/:id/agent` route
- 3-column desktop agent workspace
- mobile tabbed workspace
- conversation + timeline + workflow graph + context rail

Acceptance:

- complex multi-step tasks do not feel cramped in the side panel
- user can inspect current run without leaving the agent page
- project detail agent tab links to the dedicated page

### Phase 3: Platform Visual System Cleanup

Files:

- `apps/web/src/features/dashboard/dashboard-page.tsx`
- `apps/web/src/features/projects/project-list-page.tsx`
- `apps/web/src/features/projects/project-detail-page.tsx`
- `apps/web/src/features/settings/provider-settings-page.tsx`
- shared UI components in `apps/web/src/components/ui/`

Deliverables:

- replace colorful stat icon chips with neutral metrics
- remove lime/blue decorative gradients from guide and workflow banners
- consolidate project detail tabs into grouped navigation
- make provider settings feel like account configuration, not a plugin marketplace
- ensure light and dark themes share one brand identity

Acceptance:

- no arbitrary blue/amber/violet/emerald dashboard decorations
- no lime-gradient operational cards
- selected/active states use one product accent
- provider config dialog fits inside the page and modal viewport
- visual hierarchy is readable without relying on saturated color

### Phase 4: Public and Auth Page Alignment

Files:

- `apps/web/src/features/landing/landing-page.tsx`
- `apps/web/src/features/auth/*`
- `apps/web/src/features/pricing/pricing-page.tsx`
- `apps/web/src/features/docs/docs-page.tsx`
- `apps/web/src/components/layout/Nav.tsx`

Deliverables:

- public pages align with platform brand
- auth pages no longer feel disconnected or over-dark
- pricing/docs reuse product navigation language

Acceptance:

- public to logged-in transition feels like one product
- signup/login contrast passes in both themes
- pricing/docs do not feel like separate templates

## Component Library Position

### shadcn/ui

Continue using shadcn/ui as the base. The project already has `components.json` with `base-nova`, Tailwind v4, and lucide. Do not migrate away in this phase.

### assistant-ui

Keep `@assistant-ui/react` available, but do not wholesale replace the current panel until the event contract is stable. The immediate value is in borrowing composition ideas, not switching runtime again.

### AI SDK Elements

Use AI Elements as reference for message, prompt input, tool, reasoning, task, and attachment patterns. Do not add it as a dependency unless a later implementation plan proves it reduces code and fits the existing shadcn setup.

### React Flow

React Flow remains the workflow visualization base.

## Implementation Rules

- Before Phase 1 implementation, fix or intentionally decide the `pnpm-workspace.yaml` `allowBuilds` placeholders so standard `pnpm --filter @docpilot/web test` commands are usable again. Until then, direct package-local Vitest commands are acceptable for targeted checks.
- Do not do broad visual rewrites without tests and screenshot checks.
- Keep changes scoped by phase.
- Preserve existing API contracts unless backend work is explicitly planned.
- Introduce shared primitives only when at least two high-impact pages need them.
- Avoid one-off inline `style` except for CSS-variable driven values.
- Prefer semantic tokens over raw colors.
- Do not use provider logos from third-party URLs in production without fallback and caching strategy. Current favicon-based approach is acceptable for prototype but should be hardened later.

## Test and Verification Plan

Unit/component:

- assistant turn ordering
- activity detail sanitization
- attachment rendering
- workflow node status rendering
- provider modal viewport behavior

Build:

- `apps/web` Vite build

Browser smoke:

- login
- dashboard
- projects list
- project detail tabs
- assistant side panel
- dedicated agent workspace
- provider settings
- mobile assistant/workspace layout

Visual review:

- light theme
- dark theme
- 1366px desktop
- 1920px desktop
- 390px mobile

## Risks

- Re-theming all tokens at once can break contrast on older pages.
- Replacing assistant UI runtime before event contracts stabilize can reintroduce ordering bugs.
- A too-pretty agent page can reduce operational clarity.
- External provider logos can fail or leak visual inconsistency.
- Workflow graph can become unreadable if every detail is placed directly on nodes.
- Long-running streams need graceful disconnected/reconnecting states.

## Recommended Next Step

Implement Phase 1 first. It provides the highest visible quality lift without a full product rewrite:

1. token cleanup
2. assistant activity prelude polish
3. attachment card polish
4. workflow graph visual-state upgrade
5. agent tab as gateway to a dedicated workspace plan
