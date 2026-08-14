# BidPilot Frontend V2 Design Contract

> Status: approved design direction for the parallel V2 rebuild.
> This file is the OpenDesign-style brand and interaction contract. Every V2
> screen, component, fixture, and visual regression test must be checked
> against it before it can replace the current frontend.

## Product stance

BidPilot is an enterprise bid-execution workbench, not a generic chatbot and
not a marketing landing page wearing a dashboard shell. A user should always
understand four things at a glance:

1. which bid project they are in;
2. what material and evidence the project contains;
3. what the system or a teammate is doing now;
4. what decision or review is required next.

The visual character is quiet, precise, and dense enough for repeated work.
Motion signals state changes; it never decorates empty space.

## Visual direction

### Tone

- Calm enterprise workbench, closer to a high-quality developer tool than a
  consumer chatbot.
- Dark mode: graphite surfaces with restrained indigo and violet only for AI
  activity, focus, and primary actions.
- Light mode: cool paper background, charcoal text, blue-violet accents.
- Never use fluorescent lime as a default platform accent. Green is reserved
  for verified success; amber for attention; red for a failed or destructive
  operation.
- Do not use gradient orbs, decorative glow blobs, faux-terminal decoration,
  colorful left borders, or nested card stacks.

### Typography

- Use the existing Geist variable family for UI and prose.
- UI labels use stable 13-14px sizing and normal letter spacing.
- Display hierarchy comes from weight, line-height, and whitespace, not huge
  headings or aggressive gradients.
- Long identifiers, filenames, and tool details must wrap or truncate with an
  explicit reveal affordance; they must never force a layout wider.

### Tokens

| Token group | Light | Dark | Use |
| --- | --- | --- | --- |
| Canvas | cool near-white | graphite near-black | page background |
| Surface | white / blue-grey 2% | graphite 4-8% | panels and inputs |
| Divider | low-contrast blue-grey | low-contrast slate | structural boundaries |
| Primary | indigo-blue | blue-violet | direct user command and focus |
| Agent running | blue-violet | blue-violet | live execution only |
| Success | muted emerald | muted emerald | completed / verified |
| Attention | amber | amber | approval / blocked state |
| Danger | muted red | muted red | failed / destructive operation |

No route may define its own primary palette or shadow recipe.

## Application information architecture

### Global navigation

The authenticated product has one clear workbench navigation. Public marketing,
pricing, and documentation are outside the workbench and never compete with
daily task navigation.

1. Overview
2. Projects
3. Agent Desk
4. Knowledge
5. Runs
6. Team and settings in a separate lower management group

The active entry uses background and type contrast only. It must not use a
left bracket, colored bar, or a duplicated icon treatment. Collapsing the
sidebar preserves icon targets and tooltips; it must never visually cover the
main content.

### Project workspace

Project detail is a contextual workbench, not twelve equal tabs. Its primary
areas are:

1. Project overview and next action
2. Sources and material bundles
3. Requirements and evidence
4. Drafts
5. Review
6. Deliverables
7. Audit

Secondary controls live in page menus or project settings. The user should not
have to scan an alphabet of unrelated tabs before starting work.

### Agent Desk

`/agent` is an independent full-page workbench. The floating assistant is only
a lightweight entry point outside this page.

Desktop layout:

- conversation history: 252-296px, resizable and independently scrollable;
- conversation canvas: 640-900px readable measure;
- optional context rail: 280-360px, shown only when it adds project evidence,
  approval, artifact, or active-run value;
- composer is aligned to the conversation canvas, never stretched to the
  browser edge.

Mobile layout:

- one surface at a time: thread, history drawer, or context drawer;
- composer remains above safe-area inset;
- no desktop side panel may overlay the message body.

## Agent interaction design

### Message model

Conversation text, execution trace, approval forms, artifacts, and errors are
separate visual primitives. A raw JSON payload, internal tool identifier, or
backend stack trace must never appear in the default user-facing transcript.

### Trace-first execution

During a run, the first assistant-owned surface is a compact live execution
summary: running label, elapsed time, current action, stop control, and an
expand affordance. It grows into an ordered trace only when needed.

Trace hierarchy:

1. Run summary: plan, number of actions, status, elapsed time.
2. Phase row: e.g. "Read project context" or "Create draft".
3. Action row: friendly label, concise result, duration, status.
4. Optional detail: safe arguments, source links, artifact links, or an error
   explanation. Details are collapsed by default after completion.

Running actions display a single quiet spinner and a subtle blue-violet pulse.
Completed action rows become still. Failed actions expand once and expose a
clear recovery command. The trace is chronological; it is not a stack of
large cards at the bottom of the chat.

### Human-in-the-loop

Approval is a named interruption, not assistant prose asking a vague question.
The UI must show:

- what will happen;
- affected project, files, or cost;
- risk level;
- approve, reject, and optionally edit input;
- the outcome appended to the same run trace.

The sandbox/permission selector may be available in the composer menu, but a
permanent explanatory sentence about permissions must not consume composer
space.

### Composer

- One clear input surface with attachment tray above its text area.
- Send becomes stop while a cancellable run is active.
- Attachments are visual objects, not filename text inside the message bubble.
- Model, reasoning effort, and permission mode live in compact menus below or
  beside the input. Reasoning labels are exactly `low`, `medium`, `high`,
  `extra`, and `max` in every locale.
- User messages have restrained neutral surfaces; do not use saturated chat
  bubbles as the primary visual language.

## Motion and feedback

- Use motion only for entering a message, live progress, opening a trace, and
  changing workspace context.
- Duration: 140-220ms for direct interactions, 260-360ms for a panel change.
- Respect `prefers-reduced-motion`.
- No perpetual animations except a currently running action. No scroll reveal
  animation in operational pages.
- Loading uses a stable skeleton that preserves dimensions, not a blank white
  screen or whole-page remount.

## Engineering contract

- V2 uses one token source, one app shell, and one component ownership path.
- Keep React/Vite, TypeScript, TanStack Query, Base UI/shadcn primitives, and
  the existing FastAPI API client. Do not add a second router or a second
  global CSS framework.
- `assistant-ui`, AI Elements, or other libraries may only be adopted through
  a contained proof of concept against the real Agent Run event contract.
- Business state remains in API/domain modules. The UI owns presentation state
  only.
- Every screen has explicit empty, loading, error, populated, and narrow
  viewport states.

## Visual acceptance gates

Before a V2 surface is integrated, verify screenshots at 1440px, 1024px,
768px, and 390px widths:

- no text, controls, messages, or drawers are clipped or covered;
- no horizontal page scroll is introduced;
- fixed surfaces do not obscure composer actions;
- a real run, approval, error, and cancelled run all have intentional UI;
- keyboard focus, Escape, Enter, and touch targets work;
- loading a route does not blank the entire application shell.

## Explicit rejection list

- Continue patching V1 route by route.
- Per-page visual themes or arbitrary accent colors.
- Raw tool traces and server errors in the transcript.
- Full-page reload behavior for internal navigation.
- A marketing hero visual language inside authenticated workbench pages.
- Deploying an unreviewed visual change straight to the public site.
