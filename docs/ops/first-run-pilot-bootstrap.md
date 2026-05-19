# First-Run Pilot Bootstrap

## Goal

Bring up a fresh DocPilot environment for a controlled pilot without depending on the demo seed user.

## Prerequisites

- container infrastructure is running (`docker compose up -d`);
- production-shaped secrets are injected per `docs/development/configuration-and-secrets.md`;
- `python scripts/production_readiness.py --target production` passes when running against the pilot environment.

## Steps

1. Apply database migrations:

```powershell
uv run --directory services/api alembic upgrade head
```

2. Provision the first admin user (idempotent, safe to re-run):

```powershell
$env:DOCPILOT_BOOTSTRAP_ADMIN_PASSWORD = "<strong-random-password>"
python scripts/bootstrap_admin.py --email pilot-admin@example.com --display-name "Pilot Admin"
```

To promote an existing non-admin user instead of creating a new one, add `--promote`:

```powershell
python scripts/bootstrap_admin.py --email member@example.com --display-name "Existing Member" --promote
```

3. Confirm the admin can log in at `<DOCPILOT_APP_URL>/login` and can see the `Audit` and `System` tabs on a project detail page.

4. Run the release rehearsal core gate against the pilot environment:

```powershell
python scripts/release_rehearsal.py --run
```

5. Run the load smoke against the pilot API:

```powershell
python scripts/load_smoke.py --base-url <pilot-api-url> --requests 20 --concurrency 4
```

6. Take and verify a backup before opening the environment to pilot users:

```powershell
python scripts/backup.py backup
```

7. Hand off according to `docs/product/pilot-readiness-checklist.md`.

## Safety rules

- `bootstrap_admin.py` will refuse to silently elevate an existing non-admin user; pass `--promote` only when the elevation is intentional and recorded.
- `bootstrap_admin.py` is idempotent: re-running with the same email and an existing admin reports `already_admin` without overwriting the password.
- Never commit the bootstrap password to the repository; pass it through `--password`, `DOCPILOT_BOOTSTRAP_ADMIN_PASSWORD`, or the interactive prompt.
