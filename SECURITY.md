# Security Policy

## Scope

BidPilot is an open-source, self-hostable reference implementation. Security
reports are welcome for the API, worker, Pi bridge, authentication, project
authorization, file handling, exports, deployment scripts and documentation
that could cause a user to expose data or credentials.

## Supported version

Only the latest commit on the default branch and the currently published
deployment are treated as supported. Older commits are useful for historical
replay but should not be deployed without the current readiness and migration
checks.

## Reporting a vulnerability

Please do not open a public issue for an unpatched vulnerability. Use a private
GitHub Security Advisory at:

<https://github.com/AVIDS2/BidPilot/security/advisories/new>

Include the affected commit or deployment, the impact, a minimal reproduction,
and whether the issue involves credentials or private project data. Do not
include live keys, passwords, private documents or unredacted logs in the
report. Replace them with placeholders and state which secret class was
affected.

If private advisories are not enabled on a fork, contact the repository owner
through a private channel before publishing technical details.

## Credential handling

- Never commit `.env`, `.env.local`, production backups, database dumps, cloud
  credentials, provider API keys, JWT/Fernet secrets or MinIO/S3 credentials.
- Treat a key shown in chat, a screenshot, a terminal recording or a CI log as
  exposed even when it never entered Git. Revoke it and issue a replacement
  before making a repository public.
- Keep provider keys server-side. The browser must not receive `MIMO_API_KEY`,
  `OPENROUTER_API_KEY`, Supabase secret/service keys, database URLs or bridge
  secrets.
- Use the example environment files only as templates. Production readiness
  rejects development defaults, localhost endpoints and placeholder secrets.

## Pre-publication audit status

The 2026-09-04 repository audit found no current-environment credential match in
the working tree or Git history. It did find one old provider-key-shaped value
in development documentation in commit `bcd2fb3c`, repeated five times. The
value is absent from the current tree and does not match the currently
configured MiMo, OpenRouter or Supabase credentials, but it remains a history
exposure until the provider credential is revoked/rotated and the public refs
are rewritten and rescanned. Do not make the repository public before that
remediation is complete.

## Disclosure

The maintainer will confirm receipt, reproduce the issue, coordinate a fix and
publish a short redacted advisory when disclosure is appropriate. Please allow
time for a patch before public disclosure.
