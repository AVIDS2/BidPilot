# Workbench IA and Run Center

## Why this slice exists

The authenticated product had one real work surface, `Projects`, while Agent
activity and long-running workflow state were dispersed across project tabs and
the contextual side panel. The product needed a real operator workspace and a
safe cross-project view of durable work, not more account-style navigation or
mock dashboard cards.

## Decisions

- `/agent` is a full-page surface that reuses the existing Assistant provider,
  conversations, approval state, attachments, and runtime event stream. It is
  not a second chat client.
- Navigation now separates Workbench, Execution, and Administration. Public
  Docs/Pricing are not primary authenticated work links.
- `/runs` is the first Execution surface. It reads durable `RuntimeRun` and
  `RuntimeEvent` records, not LangGraph checkpoint tables or client-created
  state.
- Aggregate runtime rows use a separate public schema. They deliberately omit
  trace IDs, policy snapshots, input/result JSON, provider IDs, error internals,
  and event payloads.
- Non-admin callers see only project rows for projects they can already read,
  plus their own non-project Agent runs. The existing platform-admin project
  bypass remains aligned with single-run access. Deleted-project runs are never
  re-exposed by the aggregate list.

## Implementation

- Added `GET /runtime/runs?limit=` with a bounded permission-scoped query and
  the last redacted event summary.
- Added `/runs`, with status filters, safe event replay, and links back to the
  proper project or governed Agent context.
- Replaced the dashboard's per-project run polling loop with the aggregate
  runtime query.
- Added the Agent full-page route and context handling so project authority is
  route-derived and cannot leak from a previous project into global work.
- Replaced dashboard `auto-fit + min()` inline track definitions with explicit
  responsive grid layouts. This avoids browser-dependent card collapse when
  sidebars or narrow content areas coexist.

## Verification

- API runtime/Assistant regression subset: `77 passed` on `docpilot_test`.
- Run Center authorization and public-schema tests: `2 passed`.
- Web component tests for Agent context, Agent panel, and Run Center: `27
  passed`.
- TypeScript check, targeted Ruff check, production web build, and targeted
  `git diff --check` passed.

## Remaining evidence

- Capture an authenticated deployed-browser trace after the next intentional
  deployment. Local foreground development servers are not retained as release
  evidence.
- Implement aggregate Requirements, Knowledge, Reviews, and Deliverables only
  after each has an equivalent project-scope authorization contract.
