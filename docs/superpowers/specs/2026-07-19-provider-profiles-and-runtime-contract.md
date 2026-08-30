# BidPilot Provider Profiles and Runtime Contract

- Status: Approved implementation plan
- Date: 2026-07-19
- Depends on: `2026-07-18-provider-reliability-and-failure-contract.md`

## Problem

The current `provider_config` data model records only `provider_type`
(`openai` or `anthropic`) and a user-supplied `api_url`. This is insufficient
to safely support real providers:

1. API configuration, assistant planning, and workflow model calls do not use
   the same URL resolution path.
2. Workflow adapters can POST to a configured base URL rather than the final
   chat endpoint.
3. All OpenAI-compatible providers are treated as if they use the same
   authentication header and support `GET /models`.
4. A visual preset is not persisted, so runtime behavior cannot know whether a
   selected endpoint is official DeepSeek, MiMo, a DashScope compatible-mode
   endpoint, or a generic gateway.

This creates a dangerous product mismatch: a configuration can look valid in
the UI but fail only after a workflow has consumed queue capacity and a user
has uploaded sensitive bid material.

## Decision

### Persist protocol and provider profile separately

`provider_type` remains the transport protocol:

- `openai` for OpenAI-compatible Chat Completions;
- `anthropic` for Anthropic Messages.

`provider_id` is added as a stable, server-validated compatibility profile.
Existing configurations are migrated by URL inference and otherwise become
`custom-openai` or `custom-anthropic`.

The profile is a versioned application catalog, not a user-editable database
table. It contains only public integration metadata, never credentials.

### One server-side resolution boundary

Every operation resolves a `ResolvedProvider` from the same module before an
HTTP call is made:

- chat endpoint URL;
- model-list URL or an explicit unsupported result;
- request headers;
- protocol;
- safe capabilities such as native reasoning controls.

The API test endpoint, model discovery endpoint, Assistant runtime, workflow
section drafter, parser, and reviewer must all cross this boundary. No caller
may append `/chat/completions`, `/v1/messages`, or `/models` itself for a BYOK
configuration.

### Profiles in the first supported catalog

| Profile | Protocol | Authentication | Model discovery |
| --- | --- | --- | --- |
| `custom-openai` | OpenAI compatible | Bearer | Standard `GET /models`, best effort |
| `openai` | OpenAI compatible | Bearer | Supported |
| `deepseek` | OpenAI compatible | Bearer | Supported |
| `deepseek-anthropic` | Anthropic Messages | `x-api-key` | Uses documented DeepSeek model API, not a guessed Anthropic subpath |
| `dashscope` | OpenAI compatible | Bearer | Manual model selection until a documented compatible list endpoint is available |
| `doubao` | OpenAI compatible | Bearer | Manual endpoint ID selection |
| `anthropic` | Anthropic Messages | `x-api-key` plus `anthropic-version` | Supported |
| `zhipu` | OpenAI compatible | Bearer | Manual model selection |
| `minimax` | OpenAI compatible | Bearer | Manual model selection |
| `siliconflow` | OpenAI compatible | Bearer | Supported |
| `openrouter` | OpenAI compatible | Bearer | Supported |
| `mimo` | OpenAI compatible | `api-key` or Bearer | Manual model selection; direct-balance default |
| `custom-anthropic` | Anthropic Messages | `x-api-key` plus `anthropic-version` | Standard `GET /v1/models`, best effort |

"Manual" is an explicit product state, not a failed `GET /models` request.
The UI must explain that the user should select an official model or endpoint
identifier from the provider console. It must not expose raw provider error
bodies to claim discovery worked.

### Profile capabilities are conservative

Compatibility does not mean feature equivalence. The runtime sends provider
specific reasoning parameters only when the profile documents support for
them. Otherwise, reasoning level remains a prompt policy rather than a
possibly rejected request field.

For unknown custom gateways, the product uses only the base protocol contract
and does not infer vendor extensions from model names or URL fragments.

### Failure contract

Connection tests and model discovery return safe, actionable error classes:

- `provider_auth_failed`
- `provider_endpoint_invalid`
- `provider_model_unavailable`
- `provider_models_unsupported`
- `provider_timeout`
- `provider_unavailable`
- `provider_response_invalid`

The backend never returns credentials, Authorization headers, prompts, or raw
provider error responses. API clients receive a stable public message and an
optional documented model-discovery state.

## Official source checks

The initial catalog is grounded in provider documentation checked on
2026-07-19:

- OpenAI documents `GET /models` for its model list.
- Anthropic documents `GET /v1/models` and `POST /v1/messages`.
- DeepSeek documents OpenAI-compatible model listing and its Anthropic-format
  base URL, with `x-api-key` support.
- DashScope documents OpenAI-compatible Chat Completions under
  `compatible-mode`; no compatible `GET /models` contract is assumed.
- SiliconFlow and OpenRouter document model-list APIs.
- MiMo documents OpenAI compatibility using the `api-key` request header and
  user-specific base URLs.
- Volcengine Ark exposes endpoint management separately from chat inference,
  so the user-selected endpoint ID is treated as manual configuration.

Source URLs are stored in the profile catalog and displayed in the UI. They
are operational references, not runtime dependencies.

## Migration and compatibility

1. Add non-null `provider_id` with a safe temporary default.
2. Backfill known existing URLs to their matching catalog profile.
3. Backfill all remaining records from their transport protocol to the
   corresponding custom profile.
4. Keep `api_url` as the user-facing "Base URL or full endpoint" field for
   API compatibility. The resolver accepts either shape.
5. Do not automatically rewrite a user's stored URL or model name.

## Non-goals

- automatic cross-provider failover;
- unverified support for every marketplace provider;
- sending provider keys to the browser;
- probing arbitrary model URLs at save time;
- automatically discovering proprietary control-plane endpoint IDs;
- treating a successful `GET /models` response as proof that a specific model
  can complete a bid workflow.

## Acceptance criteria

- a DeepSeek Anthropic configuration resolves to the documented Messages
  endpoint for both Assistant and Workflow calls;
- a configured OpenAI-compatible base URL never receives a POST at its bare
  base path;
- MiMo requests use its documented authentication header;
- model discovery shows an explicit supported or manual state per profile;
- saved profile IDs remain encrypted-key compatible and are included in masked
  read responses;
- a provider URL only has one canonical resolution path across API, Assistant,
  and Worker code;
- tests cover URL resolution, headers, unsupported discovery, migration
  backfill, API CRUD, Assistant client construction, and worker invocation.

## Residual release gate

Automated tests use fake provider responses. Before a production release, run
one opt-in, low-token connection test against each advertised official profile
with a deliberately separate test credential and record only safe result
metadata. Do not run these probes against a user's saved key without their
explicit action in the product.
