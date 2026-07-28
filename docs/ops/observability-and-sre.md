# Observability and SRE

## Objective

DocPilot should make AI execution inspectable, not mysterious.

## Telemetry pillars

### Logs

Every service must emit structured logs with:

- timestamp
- service
- environment
- request or run ID
- project ID when available
- actor ID when available

### Metrics

Key metrics:

- API latency
- queue depth
- job runtime by type
- parse success rate
- draft success rate
- review turnaround time
- export success rate
- token and cost usage

### Traces

Trace boundaries:

- user request
- execution run
- tool call
- provider call
- parser pipeline

### Runtime Diagnostics (P0)

`RuntimeRun` is the P0 correlation root. A production support investigation
starts from one `run_id`, then follows only durable, access-controlled records:

- parent/child RuntimeRuns and their redacted RuntimeEvents;
- RuntimeAction and RuntimeApproval state, including policy outcome and wait
  time, but never action arguments, edited arguments, results, or exception
  messages;
- ExecutionRun retry lineage, TaskOutbox delivery attempts, ModelUsageRecord
  token counters, EvidenceSet/retrieval metrics, project AuditEvent links and
  produced deliverable version references.

Users consume the normal runtime event/replay surfaces. The administrator-only
diagnostic endpoint is:

```text
GET /ops/runtime-runs/{run_id}/diagnostics
```

It returns opaque request/user/organization references rather than their raw
identifiers. It must never return prompt text, attachment content, retrieval
queries, evidence quotes, tool arguments/results, provider credentials or raw
exception text. Project-scoped capability completion writes a small audit
correlation payload (`runtime_run_id`, `trace_id`, `runtime_action_id`,
capability and stable status/code) rather than duplicating business payloads.

Provider-reported token counts are aggregated when available. P0 does not
manufacture a monetary total: `cost_status=provider_cost_not_reported` means
the amount is unknown, not zero. A later billing/tracing integration may add a
priced provider receipt without changing the user-facing runtime trace.

## SLO draft

### Availability

- API availability: `99.5%`
- worker success for non-provider failures: `99.0%`

### Workflow

- parse completion for standard bundles under target size: `95% within 15 minutes`
- section draft completion: `95% within 5 minutes`

### Quality

- every generated section must store at least one evidence record or explicit missing-evidence marker

## Alert examples

- queue depth above threshold for 10 minutes
- parse failure rate above 10% over 15 minutes
- export failure on approved deliverables
- p95 API latency above threshold
- storage write failures
- `runtime_failed_<category>` from a terminal RuntimeRun diagnostic
- `runtime_stalled` for queued/running work beyond the configured support
  threshold
- `worker_task_failed`, `retry_observed`, or
  `retrieval_candidate_metrics_missing` from the same diagnostic response
- `provider_cost_not_reported` as a visibility gap to resolve before claiming
  monetary cost reporting

## Runtime Triage Path

1. Use `/ops/health-detailed` and `/ops/runtime-summary` to determine whether
   the incident is system-wide or isolated.
2. Obtain the affected `run_id` from the user-visible run history, worker task
   record, or a support report.
3. Call `/ops/runtime-runs/{run_id}/diagnostics` as an administrator and use
   its stable `error_code`, `failure_category`, retry totals and alert codes to
   choose the owner: API/runtime, provider, worker/queue, retrieval, approval,
   or input validation.
4. Correlate service logs by `run_id`, `execution_run_id` and `trace_id`; do
   not paste diagnostic payloads or model data into tickets.
5. Retry only through the governed runtime/workflow command after the cause is
   known. Record the resulting audit/run outcome for the incident review.

## Evaluation loop

Evaluation is part of operations, not only research.

Store:

- scenario
- prompt version
- provider
- expected rubric
- score outputs
- reviewer override

Use evals to compare:

- provider changes
- parser changes
- chunking changes
- retrieval settings

## Operational review cadence

- daily: backlog and failure review
- weekly: cost and quality review
- release-based: regression review before promotion
