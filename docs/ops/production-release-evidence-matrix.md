# Production Release Evidence Matrix

## Purpose

This is the promotion record for a controlled BidPilot pilot or public release.
It distinguishes source-code checks from evidence that can only be produced by
the actual target environment. A local green build is necessary, but never
substitutes for a production claim.

Store release evidence outside the repository, for example under
`/app/bidpilot/release-evidence/<git-commit>/` on the deployment host or in a
restricted CI artifact store. Do not place API keys, customer documents,
access tokens, database URLs, or raw model payloads in the evidence directory.

## Required Evidence

| Gate | Owner | How to produce it | Retained evidence | Pass condition |
|---|---|---|---|---|
| Source rehearsal | Release owner | `python scripts/release_rehearsal.py --run --output-file output/release-evidence/source-rehearsal.json` | CI job URL or redacted source-rehearsal JSON with commit SHA | migrations, static checks, API/Worker tests, web typecheck/tests/build pass |
| Agent quality | Product + reviewer | `uv run python scripts/run_quality_gate.py ... --mode release --expected-git-commit <sha>` | `quality-gate.json`, `quality-gate.md`, reviewed artifact reference | reviewed BidBench, RetrievalBench, MemoryBench, and AssistantBench captures share one evidence set/capture id; two-person review, attestation pointer, fresh reports, and every threshold pass |
| Secret/config readiness | Deployment owner | inject server secrets, then `python scripts/production_readiness.py --target production` inside the API container | redacted command result and secret-store change reference | no development defaults, required secrets present, PostgreSQL checkpointers and governed Operator enabled |
| Dependency startup | Deployment owner | `/app/bidpilot/deploy.sh`, then `docker compose ps` and container logs | compose status and one-shot job logs | readiness, migration, and checkpoint jobs complete; API/Worker/Redis/PostgreSQL/object storage are healthy |
| Public HTTPS smoke | Deployment owner | `python scripts/load_smoke.py --base-url https://bidpilot-api.rglens.com --endpoint /health --endpoint /health/ready --require-https --requests 20 --concurrency 4 --max-error-rate 0 --max-p95-ms 1000 --output-file <evidence>/api-load-smoke.json` | `api-load-smoke.json` | liveness and dependency readiness pass over HTTPS; artifact has no credentials |
| Authenticated golden path | Product owner + non-developer reviewer | create project, stage/upload bundle, ingest, draft, review, export, and download through the deployed UI | redacted screen recording, test account ids, exported checksum, audit/runtime ids | one end-to-end BidPilot workflow succeeds with source attribution and no bypass of approval/access policy |
| Recovery drill | Deployment owner | follow `docs/ops/backup-restore-drill.md` against an isolated restore target | backup checksum, restore log, verification checklist, elapsed time | restored project, approved versions, audits, and export history are visible within the declared RTO/RPO |
| Operational readiness | Operations owner | inspect logs, queue depth, provider failures, and configured alerts | dashboard snapshot or alert test record | no active P0/P1 incident; alert/rollback owner and support contact are named |

## Explicit Non-Substitutions

- A synthetic development benchmark is not release-quality evidence.
- A passing unit test for a failure mode is not proof that the production
  dependency is reachable.
- A server `.env` file existing is not proof that its secret values are valid
  or rotated.
- A successful deployment is not proof that a real user can complete the
  governed workflow.
- A backup job completing is not proof of a restore.

## Controlled Pilot Decision

A controlled pilot can proceed only when every required row has a retained
artifact for the exact Git commit, and known deviations are explicitly waived
by the release owner with an expiry date. Public paid launch additionally needs
the commercial controls documented in
`docs/product/commercial-launch-gap-analysis.md`.

## Current Code-Backed Baseline

The repository can presently provide the source rehearsal, static release
gates, redacted quality-gate format, Redis-backed fail-closed login/resend and
global API limiting in production, trusted-proxy header handling, and a
credential-safe HTTPS smoke artifact. The other rows require real CI/VPS
execution and human review; they must remain marked as pending until that
evidence exists.
