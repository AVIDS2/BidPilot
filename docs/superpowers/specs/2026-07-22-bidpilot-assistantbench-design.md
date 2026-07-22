# BidPilot AssistantBench Design

- Status: implementation baseline complete; reviewed production capture pending
- Date: 2026-07-22
- Depends on: Unified Runtime v1, Capability Registry, Runtime Policy

## Problem

BidPilot has durable runtime runs, capability policy, approval records, and a
deterministic local router. It does not yet have a repeatable answer to these
questions:

- did the Agent select the intended platform capability?
- did it ask for missing project or object scope instead of guessing?
- did it apply the same approval decision as the capability policy?
- did a destructive request retain typed confirmation?
- did a routing/prompt/model change regress a known user task?

Unit tests cover individual branches, but they are not an evaluation baseline.
An enterprise Agent needs both: unit tests protect code paths; an offline task
set protects observable task behavior and safety policy.

## Decision

Introduce `AssistantBench`, an offline, versioned evaluation harness for the
**router plus policy boundary**. It is not a benchmark of free-form prose, and
it never invokes a model during scoring.

The current Operator is a bounded router -> capability -> approval/workflow
system, not a supervisor or autonomous multi-agent team. The benchmark
therefore evaluates router and policy behavior directly. A model-backed
candidate is captured into the same schema from durable Operator records; the
deterministic local adapter remains only a control fixture.

## Dataset Contract

Each synthetic/public case contains:

- a user request and optional project context;
- an approval mode;
- expected intent mode (`tool_action`, `workflow_trigger`, `needs_input`, or
  `answer`);
- expected capability when an action is appropriate;
- expected missing fields when scope/object information is absent;
- expected policy outcome and typed-confirmation requirement when a capability
  is selected.

Fixtures contain only synthetic or approved public user text and opaque ids.
They contain no customer documents, chat histories, provider credentials, raw
tool responses, or hidden model reasoning.

Candidate observations contain only the structured intent and policy outcome.
Captured model runs can add provider/model/latency/cost and redacted evidence
provenance. Control fixtures must be explicitly marked `control_fixture` and
cannot satisfy the controlled-capture gate.

## Metrics

The initial report measures:

1. intent-mode accuracy;
2. capability-route accuracy;
3. required-input accuracy;
4. policy-outcome accuracy against the current registry;
5. typed-confirmation safety for destructive capabilities;
6. scope-guard accuracy for project/object-bound actions;
7. unknown/forbidden capability rate.

The first gate is safety-first. A controlled capture must have no unknown
capabilities, no policy mismatch, no missed typed confirmation, and no
scope-guard violation. Route/task-success thresholds are calibrated from
reviewed regression data, not guessed from a small development fixture.

## Relationship to LangGraph

LangGraph is evaluated through the product runtime event/action contract, not
through checkpoint internals. When a model-backed Operator run is captured,
the capture adapter must derive its selected capability, policy decision,
approval result, and terminal public outcome from `RuntimeAction`,
`RuntimeApproval`, and `RuntimeEvent` records. It must not store chain of
thought, raw model payloads, or checkpoint messages.

This follows the router pattern: a simple one-time intent decision should be
measured as a router. Adding a supervisor or more agents would not solve a
tool-selection regression and is not justified by this benchmark.

The Operator now has a first-class `needs_input` plan state. It is persisted as
a redacted `plan.proposed` event, rendered as `assistant.missing_input`, and
stored for at most 30 minutes as a small continuation record containing only
the capability, redacted arguments, and missing field names. The next planner
turn receives that structured state instead of relying only on prose history.

## Runtime Capture Contract

`scripts/capture_assistant_runtime_bench.py` is an offline, explicit capture
command. A private manifest maps each benchmark case to one approved
`langgraph_operator` runtime run and, when needed, its actual project id. The
capture adapter reads only `RuntimeRun`, `RuntimeEvent`, `RuntimeAction`, and
`RuntimeApproval` and emits an `AssistantEvaluationRun` containing:

- plan mode and capability name;
- missing field names;
- argument keys, policy outcome, typed-confirmation result, and a remapped
  opaque project scope;
- operator/router version plus redacted provider/model/provenance metadata.

The manifest and runtime ids stay outside the generated candidate report. The
report excludes messages, argument values, checkpoints, raw model payloads,
tool results, customer data, and chain-of-thought. There is no public API for
runtime capture. The command requires an explicit acknowledgement and is only
for approved synthetic/public test traces.

## Initial Scope

- deterministic `classify_locally` control capture;
- durable `needs_input` planning, SSE rendering, and bounded continuation;
- read-only capture of one-plan Operator traces through a private manifest;
- `CapabilityDefinition` and `evaluate_policy` parity checks;
- project scope and required object-id cases;
- destructive project deletion and typed confirmation cases;
- no model call, database mutation, or browser interaction.

## Explicit Non-Goals

- no LLM-as-a-judge score;
- no automated prompt rewriting based on a benchmark result;
- no public production capture/export endpoint;
- no score-driven bypass of capability policy;
- no claim that a control fixture proves Agent quality or commercial readiness.

## Graduation Gate

AssistantBench is now a mandatory fourth release-quality input with a reviewed
policy. The current control fixture cannot pass that gate. A promotion still
requires reviewed regression/hidden captures from the exact Git commit, a
shared evidence chain, two-person review, an attestation reference, and real
provider/model provenance. The new capture code makes that evidence possible;
it does not fabricate it.
