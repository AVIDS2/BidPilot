# 2026-07-19: Provider Profiles and Runtime Contract

## Objective

Turn BYOK provider setup from an optimistic brand preset into a shared,
verifiable protocol contract used by API validation, Assistant execution, and
Workflow Workers.

## Root Cause Found

The API connection test normalized a provider Base URL before POSTing, but the
Workflow drafting, parser, and review adapters could POST the raw Base URL.
The same saved configuration could therefore pass one path and fail in another.
The old model-list action also assumed every OpenAI-compatible provider
supported `GET /models` with a Bearer header.

## Implemented

- Added a shared `contracts.provider_profiles` registry. It owns public
  Provider Profile metadata: transport protocol, final chat endpoint rules,
  authentication scheme, documented model-list behavior, defaults, and docs
  references. It contains no API keys or request content.
- Added a persisted `provider_id` to `provider_config`, with an Alembic
  migration that backfills known hosts and falls back safely to custom
  OpenAI-compatible or Anthropic profiles.
- Kept `provider_type` as the transport protocol so existing consumers remain
  compatible. API writes validate that profile and protocol agree.
- Routed connection tests, model discovery, legacy streaming chat, Assistant
  LangChain client construction, Workflow drafting, structured parser/review
  calls, and Worker provider lookup through the same resolver.
- Added an explicit manual model-discovery state for DashScope, Ark/Doubao,
  Zhipu, MiniMax, and MiMo rather than making undocumented model-list calls.
  OpenAI, Anthropic, DeepSeek, SiliconFlow, and OpenRouter retain documented
  dynamic discovery paths. The DeepSeek Anthropic profile uses DeepSeek's
  documented model API instead of guessing an Anthropic subpath.
- Added profile-specific headers. In particular, Worker and connection tests
  send MiMo's `api-key` header, and DeepSeek Anthropic uses the Messages
  endpoint with `x-api-key`.
- Removed raw provider response bodies from legacy chat-streaming failures.

## Official-Documentation Basis

The initial catalog was checked through official provider documentation on
2026-07-19. The sources are captured in
`2026-07-19-provider-profiles-and-runtime-contract.md` and profile metadata:

- OpenAI and Anthropic model-list APIs;
- DeepSeek OpenAI model list and Anthropic-format endpoint;
- DashScope OpenAI compatible-mode;
- SiliconFlow and OpenRouter model-list APIs;
- MiMo OpenAI-compatible `api-key` transport;
- Volcengine Ark endpoint management boundary.

## Verification

- Alembic migrated the local dedicated database to `ab1c2d3e4f5 (head)`.
- Added API contract tests for DeepSeek Anthropic endpoint/header resolution,
  MiMo authentication, manual model discovery, and safe profile inference.
- Added Worker tests proving a raw DeepSeek base URL is expanded to the final
  endpoint and DeepSeek Anthropic works across the direct adapter.
- Added Assistant and frontend tests that preserve the selected profile ID.
- Full release rehearsal passed after the schema/API change:
  API `591 passed`, Worker `113 passed`, Web `25` Vitest files / `91` tests,
  TypeScript check, production Vite build, Alembic migration, and Ruff checks.

## Residual Boundary

No real provider credentials were used for this phase. The implementation
proves request construction with fake responses; it does not prove account
entitlement, model availability, network path, or provider-side behavior for
every vendor. Before marketing a profile as production-verified, run an
explicit user-triggered low-token connection test with a separate test key and
retain only safe result metadata.
