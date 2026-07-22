# AssistantBench: Router and Policy Evaluation

## Why This Slice Exists

The governed Agent had unit tests for tools, policy, approvals, and runtime
events, but no single repeatable task set that measured whether a user request
was routed to the intended capability with the intended safety boundary. That
left a familiar Agent failure mode unmeasured: a visually plausible reply could
still choose the wrong tool, guess missing scope, or weaken confirmation.

## Delivered Boundary

- Added an offline `AssistantBench` evaluator for structured Assistant intents
  and Runtime policy outcomes. It does not call an LLM, mutate a database, or
  score chat prose.
- The development fixture covers project creation, project-scoped readiness and
  drafting, missing project context, destructive deletion, explicit deliverable
  export, provider navigation, graph extraction, and personal-memory deletion.
- The evaluator measures intent mode, capability route, required input and
  argument keys, policy parity, typed confirmation safety, project scope, and
  unknown capability routing.
- A deterministic local-router capture passes the development behavior set.
  It remains a control fixture and is rejected by
  `--require-controlled-capture`, even when every metric is 100%.
- A real controlled capture requires commit, provider, model, provenance, and
  review metadata plus perfect policy/confirmation/scope safety. This only
  establishes a baseline; it is not a release or commercial-quality claim.
- The router now recognizes project deletion as a governed capability and asks
  for project context when absent. Export requests now require a concrete
  deliverable ID instead of sending an empty project argument to the tool.

## Verification

- `13 passed` on the isolated PostgreSQL-backed Assistant and AssistantBench
  target suite.
- AssistantBench unit coverage validates router success, policy/scope regression
  detection, controlled-capture metadata, and control-fixture rejection.
- API and root Ruff checks passed; both benchmark runner scripts compile.

## Next Gate

Create a redacted RuntimeAction/RuntimeApproval capture adapter after a real
low-cost Operator run is available. Then collect reviewed regression and hidden
cases before turning AssistantBench into a release-gate input. Do not use the
deterministic fixture to claim model quality or autonomous task success.
