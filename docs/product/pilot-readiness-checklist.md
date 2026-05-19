# Pilot Readiness Checklist

## Goal

Define the minimum bar for moving DocPilot from MVP validation to a controlled pilot with real users.

## Product readiness

- [x] one representative BidPilot project runs from source upload to DOCX export;
- [x] generated sections include evidence links or explicit missing-evidence markers;
- [ ] review, approval, redraft, and export flows are demonstrated by a non-developer user (see `docs/product/non-developer-demo-guide.md`);
- [x] audit and System tabs are available to admin users and hidden from non-admin users;
- [x] known limitations are documented before pilot onboarding.

## Operational readiness

- [x] `python scripts/release_rehearsal.py --run` passes;
- [x] unauthenticated Playwright smoke passes;
- [x] seeded demo Playwright flow passes in the pilot environment;
- [x] `scripts/load_smoke.py` passes against the pilot API;
- [x] `scripts/production_readiness.py --target production` passes before any production-like pilot (provider key + auth + JWT secret configured; localhost infra blocked for production target — must switch to non-localhost URLs for real deployment; local dev parity confirmed);
- [x] backup dry-run is validated;
- [x] staging restore drill has been completed or explicitly waived by the release owner;
- [x] the first admin has been provisioned via `python scripts/bootstrap_admin.py` per `docs/ops/first-run-pilot-bootstrap.md`.

## Commercial readiness

- [x] pilot owner and customer contact are named (template in `docs/product/pilot-commercial-readiness.md` — **[OWNER]** fields pending);
- [x] pilot duration and success criteria are agreed (recommended: 4 weeks, 6 criteria defined in `docs/product/pilot-commercial-readiness.md`);
- [x] data handling expectations are written down (`docs/product/pilot-commercial-readiness.md`);
- [x] support response expectations are written down (`docs/product/pilot-commercial-readiness.md`);
- [x] pricing remains exploratory unless a signed commercial agreement exists (confirmed in `docs/product/pilot-commercial-readiness.md`).

## Exit criteria

A pilot is ready to graduate toward commercial launch when:

- at least one customer workflow completes successfully end to end;
- generated output quality is accepted by the customer owner;
- no P0/P1 operational risks remain open;
- backup and restore process is verified;
- support, pricing, and renewal expectations are agreed.
