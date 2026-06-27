# Assistant Panel UI v2 Design

## Goal

Restore the assistant panel as a trustworthy agent console instead of a generic chat skin. The panel should preserve DocPilot's existing assistant backend events while improving the visible interaction quality.

## Scope

- Keep the current `AIAssistantPanel` and `ai-assistant-store` architecture.
- Do not replace the panel with `assistant-ui` runtime in this pass.
- Render agent execution state inside the conversation flow, close to the assistant response that caused it.
- Preserve Markdown, GFM, code blocks, and KaTeX math rendering through the existing `Markdown` component.
- Improve bottom input ergonomics, scroll-to-bottom placement, and busy/empty states.
- Keep history as an overlay, not a layout-pushing sidebar.

## Interaction Model

Assistant responses are message-first. Tool calls, workflow runs, and confirmation prompts appear as inline agent activity below the current assistant turn, not as a detached top-level status strip.

The header only shows durable context: conversation title, history toggle, new chat, command mode, and close. Transient execution details belong in the scrollable message area.

## Visual Direction

The panel is a compact B2B agent cockpit:

- semantic theme tokens only;
- soft cards with strong text contrast;
- no new global palette;
- no emoji-based affordances;
- clear running/succeeded/failed states;
- mobile-safe width and bottom input.

## Verification

- Unit tests should prove inline execution cards render inside the message stream.
- Markdown tests should continue proving math rendering works.
- Build must pass before deployment.
