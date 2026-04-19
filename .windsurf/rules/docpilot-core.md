---
trigger: always_on
---

# DocPilot Core Rule

- Keep this repository on the documented primary stack unless the ADRs are updated.
- Prefer checking `Context7`, project source, or official docs before using unfamiliar APIs or CLI flags.
- For `shadcn/ui` work, prefer `shadcn` tooling or MCP before hand-rolling component usage.
- After meaningful frontend changes, run `Playwright` when the flow is locally testable.
- Before schema-related changes, inspect migrations, models, or Postgres tooling first.
- If an API, prop, field, or integration detail is uncertain, verify it instead of inventing it.
- These are strong defaults for `DocPilot`, not rigid blockers. If one tool is unavailable, fall back to source code or official documentation and keep moving.
