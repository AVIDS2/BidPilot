# Backup and Restore Drill

## Goal

Prove that DocPilot production recovery claims are backed by an operator-practiced database backup and restore path.

## Recovery targets

Initial production targets are defined in `docs/product/non-functional-requirements.md`:

- `RPO`: 24 hours maximum
- `RTO`: 4 hours maximum

## Dry-run command validation

Use dry-run mode before touching a live database:

```powershell
python scripts/backup.py backup --dry-run
```

For a known backup file:

```powershell
python scripts/backup.py restore backups/docpilot-sample.sql --dry-run
```

Dry-run prints the `pg_dump` or `psql` command shape and validates that restore input files exist.

## Staging drill

1. Confirm staging is isolated from production.
2. Confirm `DOCPILOT_DATABASE_URL` points at the staging database.
3. Create or seed a representative BidPilot project.
4. Run:

```powershell
python scripts/backup.py backup --output-dir backups
```

5. Provision a clean staging restore target.
6. Set `DOCPILOT_DATABASE_URL` to the restore target.
7. Run:

```powershell
python scripts/backup.py restore backups/<backup-file>.sql
```

8. Validate:

- the representative project is visible;
- deliverables and approved section versions are present;
- audit events are present;
- export history remains traceable;
- health checks pass after restore.

## Production rule

Do not restore into production without explicit operator approval, a named rollback owner, and a current backup file path recorded in the release notes.
