# VPS Pilot Deployment

## Goal

Bring DocPilot up on the VPS as a controlled pilot with public HTTPS web/API domains, auth enforced, SMTP enabled, and a repeatable launch/rollback path.

## Topology

- web: static Vite build served by Nginx
- api: FastAPI
- worker: Celery
- postgres: pgvector
- redis: queue/cache
- minio: object storage

## Required environment

Use a managed secret source or an uncommitted `.env.production` file on the VPS.

Required values:

- `DOCPILOT_DATABASE_URL`
- `DOCPILOT_POSTGRES_DB`
- `DOCPILOT_POSTGRES_USER`
- `DOCPILOT_POSTGRES_PASSWORD`
- `DOCPILOT_REDIS_URL`
- `DOCPILOT_REDIS_PASSWORD`
- `DOCPILOT_RATE_LIMIT=1000/minute` (or another reviewed public API budget)
- `DOCPILOT_TRUSTED_PROXY_CIDRS` for only the direct 1Panel/OpenResty-to-API hop
- `DOCPILOT_MINIO_ENDPOINT`
- `DOCPILOT_MINIO_ACCESS_KEY`
- `DOCPILOT_MINIO_SECRET_KEY`
- `DOCPILOT_JWT_SECRET`
- `DOCPILOT_SECRETS_KEY`
- `DOCPILOT_AUTH_REQUIRED=true`
- `DOCPILOT_APP_URL=https://bidpilot.rglens.com`
- `DOCPILOT_CORS_ORIGINS=https://bidpilot.rglens.com`
- `DOCPILOT_LANGGRAPH_CHECKPOINTER=postgres`
- `DOCPILOT_AGENT_CHECKPOINTER=postgres`
- `DOCPILOT_ASSISTANT_ENGINE=pi`
- `DOCPILOT_PI_AGENT_URL=http://pi-agent:8787`
- `DOCPILOT_PI_TOOL_BRIDGE_URL=http://api:8000/internal/pi/tools/execute`
- `DOCPILOT_PI_INTERNAL_SECRET`
- `DOCPILOT_SMTP_HOST`
- `DOCPILOT_SMTP_USER`
- `DOCPILOT_SMTP_PASS`
- `DOCPILOT_SMTP_FROM`
- one provider key, such as `DOCPILOT_PROVIDER_DOMESTIC_API_KEY`
- `DOCPILOT_TURNSTILE_SECRET_KEY`
- `VITE_TURNSTILE_SITE_KEY`

If and only if paid self-service is being enabled, also configure:

- `DOCPILOT_STRIPE_SECRET_KEY`
- `DOCPILOT_STRIPE_WEBHOOK_SECRET`
- `DOCPILOT_STRIPE_PRO_PRICE_ID`
- `DOCPILOT_STRIPE_ENTERPRISE_PRICE_ID` (only if Enterprise self-service is enabled)

## Build and start

From `/app/bidpilot`, after the outer server `.env` has passed the readiness
gate:

```bash
./deploy.sh
```

The script pulls `master`, validates the versioned production Compose template
against the server `.env`, synchronizes the outer Compose file, then starts the
full pilot stack. It does not copy or print secrets.

## Database migrations

The production deploy path runs readiness validation, migrations, and LangGraph
checkpoint setup as ordered one-shot Compose services. Do not bypass them with
an ad-hoc API restart. To verify their completed state:

```bash
docker compose ps readiness migrate checkpoints
```

## First admin bootstrap

```powershell
$env:DOCPILOT_BOOTSTRAP_ADMIN_PASSWORD = "<strong-random-password>"
docker compose exec api python scripts/bootstrap_admin.py --email pilot-admin@example.com --display-name "Pilot Admin"
```

## Access

- web: `https://bidpilot.rglens.com`
- api: `https://bidpilot-api.rglens.com`

The reverse proxy should route public traffic to the web and API containers. Keep database, Redis, and MinIO internal.

## Trusted proxy and public rate limits

The API accepts `X-Forwarded-For` or `X-Real-IP` only when its immediate
network peer belongs to `DOCPILOT_TRUSTED_PROXY_CIDRS`. This prevents a public
caller from forging a forwarding header to evade API or Turnstile budgets.

- Keep the API bound to `127.0.0.1:3101` as defined in the production Compose
  file; do not expose port `8000` or the container network directly.
- Configure the value to the precise source address/CIDR that FastAPI sees for
  the 1Panel/OpenResty hop. In a Docker deployment this is often the relevant
  bridge gateway, but it must be verified for the actual host rather than
  copied from an example.
- In OpenResty, overwrite the forwarded client headers before proxying; do not
  append an untrusted incoming `X-Forwarded-For` value. If Cloudflare proxying
  is enabled, configure OpenResty's real-IP handling from Cloudflare's current
  official ranges first, then forward the resulting client address.
- The global API budget uses Redis (`DOCPILOT_REDIS_URL`) by default. Set
  `DOCPILOT_RATE_LIMIT_STORAGE_URI` only when using a separate authenticated
  Redis instance for rate limiting.

Production startup fails when the trusted proxy list or Redis-backed global
limiter is unavailable. Test the web, login, and API paths after changing this
configuration before opening the pilot.

## Stripe paid self-service

Keep Stripe disabled for a controlled free pilot unless the owner has completed
the paid-launch checklist. When it is enabled:

- register `https://bidpilot-api.rglens.com/billing/webhook` as the Stripe
  webhook destination for the API mode in use;
- use the destination-specific webhook signing secret, not the API secret;
- enable the Stripe Customer Portal for plan change, cancellation, and payment
  method management, but keep quantity changes disabled until the seat-overage
  remediation workflow is available;
- confirm `checkout.session.completed`, `customer.subscription.created`,
  `customer.subscription.updated`, `customer.subscription.deleted`,
  `invoice.paid`, and `invoice.payment_failed` reach the endpoint;
- run one Stripe test-mode checkout, portal redirect, cancellation, failed
  invoice, webhook retry, and a later successful invoice before live mode.

Follow `docs/ops/stripe-test-mode-rehearsal.md` and run its Test Mode preflight
before that sequence. The preflight validates active licensed prices without
creating a Stripe customer, Checkout Session, or subscription.

BidPilot persists only a minimal event receipt and Stripe identifiers. It
deduplicates by signed Stripe event ID and ignores a delayed event that predates
the last applied subscription state. Do not delete those receipts as a routine
cache clear; define a reviewed retention job before volume requires pruning.

## Health checks

- API liveness: `GET /health` (does not depend on Redis)
- API readiness: `GET /health/ready` (checks PostgreSQL, Redis, and object storage without returning backend error text)
- production readiness: `python scripts/production_readiness.py --target production`

## Backup and restore

Before opening the pilot to users:

```powershell
docker compose exec api python scripts/backup.py backup
```

Then run the restore drill in the designated non-production database before promotion.

## Rollback

- web can roll back independently;
- API and worker roll back together;
- database changes require backup + restore, not blind down-migrations.
