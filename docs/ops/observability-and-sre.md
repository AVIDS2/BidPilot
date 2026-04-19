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
