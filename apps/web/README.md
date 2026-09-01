# BidPilot Web

This directory contains the BidPilot user-facing web application. It uses the
Kiranism Next.js dashboard source as its frontend base and keeps BidPilot's
FastAPI control plane, Worker, PostgreSQL, Redis, object storage and Pi agent
as the runtime authorities.

## Stack

- Next.js 16 App Router and React 19
- Tailwind CSS v4
- shadcn/ui on Base UI primitives
- TanStack Query, TanStack Table and TanStack Form
- BidPilot REST/SSE client and Pi event projection

## Local commands

Run these commands from the repository root:

```bash
pnpm --filter @docpilot/web dev
pnpm --filter @docpilot/web typecheck
pnpm --filter @docpilot/web lint
pnpm --filter @docpilot/web format:check
pnpm --filter @docpilot/web build
```

The local development baseline uses direct Node and Python processes. Docker
is reserved for the VPS production topology.

## Runtime boundary

The browser calls same-origin `/api/auth/*` and `/api/bidpilot/*` handlers.
Next forwards authenticated REST, multipart and SSE requests to FastAPI using
an HttpOnly access cookie. The browser never receives provider API keys.

Set `DOCPILOT_API_URL` to the FastAPI base URL when running the web process
outside the production compose network. The production compose file uses
`http://api:8000` for this value.

## Product routes

The active application includes the public landing page, authentication flows,
dashboard, projects, requirements, knowledge, runs, deliverables, reviews,
members, account, administration, provider settings and the Pi-backed Agent
workbench.

## Source and licensing

The Kiranism dashboard source is MIT licensed; see `LICENSE`. The small landing
structure adapted from ixartz is documented in `THIRD_PARTY_NOTICES.md`.
