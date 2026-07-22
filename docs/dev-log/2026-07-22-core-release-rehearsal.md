# Core Release Rehearsal

## Scope

Ran the repository's core release rehearsal with the dedicated local `_test`
database. The rehearsal runs migrations, API and Worker static checks/tests,
frontend TypeScript, frontend unit tests, and the production web build. It
does not deploy a container, call a provider, access the VPS, or use a
production database.

## Result

The final continuous run passed:

- API migrations;
- API Ruff and `666` tests;
- Worker Ruff and `127` tests;
- frontend TypeScript;
- frontend `28` test files / `106` tests;
- production Vite build.

The rehearsal can now write an ignored redacted JSON artifact through
`--output-file`. A local artifact was generated with all eight gates passing
and no database, secret, password, API-key, token, or environment-variable
markers. It correctly records that this working tree has tracked changes, so
it is useful local evidence but not a clean-commit promotion record.

## Fix During Rehearsal

The first run exposed `dispatch is not a function` in
`app-platform-shell.test.tsx`. Production `useAIAssistant()` returns `dispatch`
for route-context updates, but the test mock predated that hook contract. The
mock now includes `dispatch`, and the authenticated public-route shell test
passes without changing production behavior.

## Browser Smoke

The public browser smoke now starts an isolated Vite server on port `5174` by
default instead of silently reusing a developer server on `5173`. The prior
configuration reused a stale local checkout, which produced an obsolete
`/auth` redirect that is not present in the current route table.

With the current source, the unauthenticated desktop and Pixel 7 smoke suites
passed with `18 passed, 22 skipped`. The skipped cases intentionally require
`E2E_DEMO=1`, a running API, and seeded demo data. This confirms public routes,
authentication-page rendering, pricing, locale selection, and unauthenticated
redirect behavior; it is not an authenticated production-workflow trace.

## Boundary

This is source-level release evidence only. The following remain mandatory for
a pilot or production claim:

- production-readiness gate with real secret-store values;
- deployed HTTPS health/load evidence;
- authenticated browser golden path with a realistic bundle;
- reviewed real-provider quality and adversarial traces;
- backup and restore drill; and
- retained CI/reviewer artifacts tied to the released commit.
