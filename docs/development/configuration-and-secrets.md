# Configuration and Secrets

## Goal

Provide one stable place for environment variables, secret ownership, and configuration discipline.

This document prevents future implementation from inventing config ad hoc.

## Configuration principles

- every new environment variable must have a documented owner and purpose
- secrets and non-secret config should be distinguishable
- local development must work with safe defaults where possible
- production secrets must never be committed to the repository

## Service configuration groups

### Web

Typical categories:

- server-only FastAPI base URL for the Next Route Handler BFF
- public application URL and cookie/session configuration
- feature flags for non-production features
- telemetry browser settings

### API

Typical categories:

- database connection
- cache or queue connection
- object storage connection
- auth settings
- provider keys and endpoints
- telemetry export settings

### Worker

Typical categories:

- queue backend
- database connection
- object storage connection
- provider and parser adapter settings
- concurrency and retry tuning
- telemetry export settings

## Baseline variables

These names are the preferred starting point for implementation.

### Shared

- `DOCPILOT_ENV`
- `DOCPILOT_LOG_LEVEL`
- `DOCPILOT_APP_URL`
- `DOCPILOT_API_URL`
- `DOCPILOT_CORS_ORIGINS`

### Next web edge

- `DOCPILOT_API_URL` (server-only URL used by `apps/web/src/lib/backend.ts`;
  use `http://127.0.0.1:8000` for direct local API and `http://api:8000` in the
  VPS Compose network)
- `NEXT_PUBLIC_APP_URL` (public URL used for metadata; never a secret)

The browser calls `/api/auth/*` and `/api/bidpilot/*` on the Next origin. The
access and refresh tokens are HttpOnly cookies; no browser bundle reads or
stores bearer tokens.

### API and worker

- `DOCPILOT_DATABASE_URL`
- `DOCPILOT_TEST_DATABASE_URL` (test runner and local release rehearsal only)
- `DOCPILOT_REDIS_URL`
- `DOCPILOT_S3_ENDPOINT`
- `DOCPILOT_S3_BUCKET`
- `DOCPILOT_S3_ACCESS_KEY`
- `DOCPILOT_S3_SECRET_KEY`

### AI adapters

- `DOCPILOT_PROVIDER_OPENAI_BASE_URL`
- `DOCPILOT_PROVIDER_OPENAI_API_KEY`
- `DOCPILOT_PROVIDER_DOMESTIC_BASE_URL`
- `DOCPILOT_PROVIDER_DOMESTIC_API_KEY`
- `DOCPILOT_PROVIDER_DOMESTIC_MODEL`
- `MIMO_API_KEY` / `XIAOMI_API_KEY` as server-only MiMo direct-balance aliases
- `MIMO_BASE_URL` / `MIMO_MODEL` as optional MiMo overrides
- `ALIYUN_API_KEY` / `DASHSCOPE_API_KEY` as local compatibility aliases for Aliyun Bailian/DashScope only
- `DOCPILOT_SECRETS_KEY`
- `DOCPILOT_LANGGRAPH_CHECKPOINTER`
- `DOCPILOT_AGENT_CHECKPOINTER`
- `DOCPILOT_ASSISTANT_ENGINE`
- `DOCPILOT_LOCAL_DIRECT_ASSISTANT` (local-only direct Pi execution switch;
  keep false/unset for production and for local environments with Worker)
- `DOCPILOT_AGENT_MEMORY_EMBEDDING_TIMEOUT_SECONDS`
- `DOCPILOT_MEM0_ENABLED`
- `DOCPILOT_MEM0_API_KEY`
- `DOCPILOT_MEM0_HOST`
- `DOCPILOT_MEM0_AGENT_ID`
- `DOCPILOT_MEM0_APP_SCOPE`
- `DOCPILOT_MEM0_TIMEOUT_SECONDS`

### Telemetry

- `DOCPILOT_OTEL_EXPORTER_ENDPOINT`
- `DOCPILOT_LANGFUSE_PUBLIC_KEY`
- `DOCPILOT_LANGFUSE_SECRET_KEY`
- `DOCPILOT_LANGFUSE_HOST`

### Security

- `DOCPILOT_AUTH_MODE`
- `DOCPILOT_JWT_SECRET`
- `DOCPILOT_SESSION_SECRET`
- `DOCPILOT_SECRETS_KEY`
- `DOCPILOT_RATE_LIMIT`
- `DOCPILOT_RATE_LIMIT_STORAGE_URI` (optional authenticated Redis override)
- `DOCPILOT_TRUSTED_PROXY_CIDRS`

### Billing (API only)

- `DOCPILOT_STRIPE_SECRET_KEY`
- `DOCPILOT_STRIPE_WEBHOOK_SECRET`
- `DOCPILOT_STRIPE_PRO_PRICE_ID`
- `DOCPILOT_STRIPE_ENTERPRISE_PRICE_ID`

## Environment strategy

### Local

- prefer `.env.local` or service-specific local env files ignored by git
- safe dummy or development credentials are acceptable
- local config should default toward developer productivity
- the concrete local baseline is defined in `docs/development/local-environment-baseline.md`

### Test execution

- API tests and `scripts/release_rehearsal.py --run` require a dedicated
  PostgreSQL database whose name ends in `_test`.
- Set `DOCPILOT_TEST_DATABASE_URL` in an ignored local environment file, or set
  `DOCPILOT_DATABASE_URL` itself to a URL ending in `_test` for CI.
- Test startup copies that value into `DOCPILOT_DATABASE_URL` before the API
  engine is imported. A normal development or production database is rejected
  before migrations or tests run.
- On a machine with an approved isolated PostgreSQL instance, create the test
  database with `uv run --directory services/api python
  ../../scripts/prepare_local_test_database.py`, then migrate it with Alembic
  before the first test run. The current Windows UI profile does not start
  Docker; use its SQLite contract profile for local page and auth checks.

## Current documented local baseline

Use the project baseline unless later docs override it:

- Python env: `conda activate llm`
- PostgreSQL: approved host/isolated instance only; the current verified UI
  profile uses ignored SQLite at `.tmp/bidpilot-local.sqlite3` because Docker is
  prohibited on the developer machine
- provider base URL: `https://dashscope.aliyuncs.com/compatible-mode/v1`
- current local provider key: `<your-api-key>`
- primary model: `qwen3.5-flash`
- multimodal embedding model: `qwen3-vl-embedding`
- text embedding model: `text-embedding-v4`

Provider keys submitted through the product are encrypted before storage. Set `DOCPILOT_SECRETS_KEY` in API and worker environments with a Fernet key generated by:

```bash
uv run --directory services/api python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Never commit this value. For Aliyun Bailian/DashScope keys, remove the default `0.0.0.0/0` and `::/0` API key whitelist entries and allow only known server egress IPs.

Official platform provider keys must stay server-side. The current preferred
BidPilot platform profile is Xiaomi MiMo direct balance: set
`DOCPILOT_ASSISTANT_PROVIDER_ID=mimo`,
`DOCPILOT_ASSISTANT_API_KEY`,
`DOCPILOT_ASSISTANT_BASE_URL=https://api.xiaomimimo.com/v1`, and
`DOCPILOT_ASSISTANT_MODEL=mimo-v2.5-pro`. MiMo uses OpenAI-compatible Chat
Completions and documents both `api-key` and Bearer authentication. The Pi
sidecar maps this product profile to its built-in `xiaomi` provider. The
shorter `MIMO_API_KEY` or `XIAOMI_API_KEY` aliases are supported for platform
fallbacks; `MIMO_BASE_URL` and `MIMO_MODEL` are optional overrides. OpenCode Go
and DeepSeek remain supported compatibility profiles, but must not be left in
the production environment when MiMo is selected. Choose one platform profile
per deployment to keep API, Worker, and assistant runs consistent. Never expose
official or user-supplied provider keys to the browser.

`DOCPILOT_OFFICIAL_MONTHLY_TOKEN_CEILING` is a required non-secret server-side
integer in staging and production. It is the per-workspace hard maximum for
platform-funded LLM and server-owned embedding tokens: API preflight and each
Worker-owned physical provider call reserve against it before provider I/O. A
workspace billing owner may set a lower `official_monthly_token_limit`, but can
never raise or remove the platform ceiling. `0` is an emergency kill switch for
platform-funded provider calls. BYOK usage is kept on its own ledger and may
use an owner-selected personal safeguard without consuming the platform
ceiling.

This is a token guardrail, not a currency price catalogue. Every server-owned
embedding request reserves a conservative upper bound before I/O and settles
once from provider-reported `usage.total_tokens`; an omitted usage field stays
reserved as uncertain rather than being treated as free. Indexing-job quotas
remain a separate product limit. Currency reconciliation, a reviewed price
catalogue, and invoice matching are still separate launch requirements.

`DOCPILOT_LANGGRAPH_CHECKPOINTER=postgres` is the production default for durable workflow checkpoints. `DOCPILOT_AGENT_CHECKPOINTER=postgres` is the corresponding durable setting for the interactive Assistant. `memory` is allowed only for explicit local smoke tests where checkpoint behavior is being isolated.

`DOCPILOT_ASSISTANT_ENGINE=pi` is the production default for new assistant turns. The Pi sidecar owns the model/tool loop and native streaming; the API remains authoritative for policy, idempotency, approval, audit, and business writes. `operator` and `streaming_harness` are historical parser aliases only and must not appear in new deployment files. There is no automatic fallback to the retired Python loop.

Pi runtime variables:

- `DOCPILOT_PI_AGENT_URL` — internal Pi sidecar URL, for example `http://pi-agent:8787`.
- `DOCPILOT_PI_TOOL_BRIDGE_URL` — API-only callback URL for governed tool execution.
- `DOCPILOT_PI_INTERNAL_SECRET` — dedicated short-lived bridge-token signing secret; production must not reuse `DOCPILOT_JWT_SECRET`.
- `DOCPILOT_INTERNAL_API_URL` — Worker-to-API internal URL for queued assistant execution and system wakes; defaults to `http://api:8000` inside Compose.

The production Pi sidecar currently accepts only the server-authored
`governed_cloud` sandbox snapshot. It loads the compiled trusted extensions
`bidpilot-governance` and `bidpilot-skills`, disables Pi host tools, and permits
business I/O only through the signed API bridge. No environment variable may
enable `bash`, arbitrary filesystem extension paths, tenant JavaScript, or
direct model-selected network access in this sidecar. `Auto-run` / `full_access`
changes optional business confirmation behavior only; it never changes this
sandbox boundary.

An `isolated_workspace` runner is a separate deployment capability and is not
enabled by configuration today. When implemented, it must be a container,
VM, or microVM with explicit mounts, egress, quotas, short-lived credentials,
and audit controls. Do not add an environment flag that simulates this boundary
inside the Pi process.

Resend is the preferred transactional email provider. Set `RESEND_API_KEY`
and, when a different verified domain is needed, `DOCPILOT_RESEND_FROM`.
The default sender is `BidPilot <notifications@updates.rglens.com>`, which must
remain verified in the Resend account. SMTP remains a compatible fallback and
is configured only when `DOCPILOT_SMTP_HOST`, `DOCPILOT_SMTP_USER`,
`DOCPILOT_SMTP_PASS`, and `DOCPILOT_SMTP_FROM` are all present. Use an app
password or provider credential rather than a mailbox's interactive login
password; a personal mailbox is suitable only for a short pilot and does not
provide the domain authentication needed for reliable production delivery.

`DOCPILOT_AGENT_MEMORY_EMBEDDING_TIMEOUT_SECONDS` defaults to `2.5` and is capped at five seconds. It applies only to optional automatic memory recall during an Agent turn: when no authorized memory exists, no embedding request is sent; when the provider is slow or unavailable, the Agent continues with lexical recall and explicit degraded state rather than blocking the conversation.

Mem0 is an optional long-term **user profile** provider, not a replacement for
BidPilot's PostgreSQL business memory. `DOCPILOT_MEM0_ENABLED` must be set to
`true` explicitly. `DOCPILOT_MEM0_API_KEY` is server-only and is consumed by
API/Worker through the official `mem0ai` SDK. Recall is scoped by the current
user, BidPilot agent id, and organization `app_id`; the timeout is bounded and
Mem0 failures are fail-open. Only low-risk preferences and communication
style may be captured. Tender files, evidence, qualifications, deadlines,
hidden reasoning, tokens, and tool payloads must remain in BidPilot's own
authorized stores. Account deletion must call the provider's scoped
`delete_all` operation as part of the privacy workflow. Mem0 user and agent
entities are separate; reads use the official OR scope filter and deletion
issues one request per entity. When `DOCPILOT_MEM0_APP_SCOPE=false`, Platform-
only `app_id` is omitted for compatible OSS/self-hosted endpoints.

Before API or Worker starts in staging or production, apply Alembic migrations and run `python scripts/setup_langgraph_checkpoints.py` once against the target database. The production Compose file performs both as ordered one-shot services: `migrate` upgrades the business schema, then `checkpoints` creates or upgrades LangGraph checkpoint tables without logging the connection URL. Runtime services only open prepared storage; they do not create business or checkpoint tables lazily.

## Trial and quota policy

Initial product policy:

- Anonymous users: no workflow generation runs.
- Logged-in starter users: 3 official-provider workflow draft runs per month as a free trial.
- Logged-in starter users: 100 official-provider assistant messages per month.
- Logged-in starter users: 5 official-provider document indexing jobs per month.
- Professional and enterprise plans are unlimited in-product, but every official
  LLM call remains below `DOCPILOT_OFFICIAL_MONTHLY_TOKEN_CEILING` and any
  lower organization safeguard.
- BYOK users: user provider keys are encrypted with `DOCPILOT_SECRETS_KEY`; provider token cost is not charged to the platform, but abuse/rate limits still apply.

Quota must be enforced in the backend before starting a workflow, creating an indexing job, or calling a paid provider. UI-only blocking is not sufficient.

## Stripe billing configuration

Stripe credentials and price IDs belong only to the API deployment environment.
They must never be prefixed with `VITE_`, returned by an API response, written to
logs, or copied into a provider configuration record.

Before enabling paid self-service, configure the following in the Stripe
Dashboard for the exact environment (test and live use separate webhook
secrets):

1. Create a recurring `licensed` Professional price and set its ID as
   `DOCPILOT_STRIPE_PRO_PRICE_ID`. Enterprise is sales-led by default; set
   `DOCPILOT_STRIPE_ENTERPRISE_PRICE_ID` only if its self-service Checkout is
   deliberately enabled.
2. Create an HTTPS webhook destination at
   `https://bidpilot-api.rglens.com/billing/webhook` and subscribe to
   `checkout.session.completed`, `customer.subscription.created`,
   `customer.subscription.updated`, `customer.subscription.deleted`,
   `invoice.paid`, and `invoice.payment_failed`.
3. Store that destination's signing secret as
   `DOCPILOT_STRIPE_WEBHOOK_SECRET`; it is not the Stripe API secret key.
4. Enable and configure Stripe's Customer Portal for payment-method updates,
   plan changes, and cancellation. Keep quantity changes disabled until the
   seat-overage remediation workflow is implemented. BidPilot reconciles a
   Portal plan switch from the Subscription item's actual configured Price ID,
   rather than trusting stale Checkout metadata, and redirects existing Stripe
   customers to the hosted portal rather than creating a second subscription.

The local billing control plane stores only Stripe identifiers, signed event
metadata needed for reconciliation, and an event receipt/outcome. It does not
store card data or raw webhook bodies. The webhook receipt table provides
replay protection; application changes must preserve it.

### Staging

- all secrets come from a managed source or deployment secret injection
- staging should mirror production contract shape even if scale differs

### Production

- all secrets come from a managed secret source
- rotation procedure must exist for provider keys, JWT secrets, and storage credentials
- secret values must not appear in logs, traces, or event payloads
- production promotion must pass `python scripts/production_readiness.py --target production`
- `DOCPILOT_AUTH_REQUIRED` must be `true` outside local development
- deployment secrets must not use localhost endpoints or documented development defaults
- `DOCPILOT_ENV` must be `production`
- `DOCPILOT_LANGGRAPH_CHECKPOINTER` must be `postgres`
- `DOCPILOT_AGENT_CHECKPOINTER` must be `postgres`
- `DOCPILOT_ASSISTANT_ENGINE` must be `pi`
- `DOCPILOT_RATE_LIMIT` must be a reviewed positive fixed-window budget such as `1000/minute`
- `DOCPILOT_OFFICIAL_MONTHLY_TOKEN_CEILING` must be a reviewed non-negative
  per-workspace platform maximum; `0` intentionally disables platform-funded
  LLM calls during an incident
- `DOCPILOT_TRUSTED_PROXY_CIDRS` must contain only the direct reverse-proxy peer addresses seen by the API; the API must remain loopback-bound behind that proxy
- If paid billing is enabled, `DOCPILOT_STRIPE_SECRET_KEY`,
  `DOCPILOT_STRIPE_WEBHOOK_SECRET`, and `DOCPILOT_STRIPE_PRO_PRICE_ID` must be
  configured for the same Stripe mode (test or live). Configure the Enterprise
  price only when self-service Enterprise Checkout is deliberately enabled.
  Production readiness rejects a Test Mode secret key when paid billing is
  enabled. The Customer Portal and webhook destination must be verified before
  opening checkout to users.

## Ownership and update rule

Every added variable should answer:

- which service uses it
- whether it is secret
- what default, if any, is allowed locally
- what breaks if it is missing or invalid

If a new subsystem introduces configuration, update this document in the same change.
