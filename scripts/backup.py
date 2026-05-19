#!/usr/bin/env python3
"""Backup and restore utilities for DocPilot PostgreSQL database."""

import argparse
import os
import subprocess
import sys
from datetime import UTC, datetime
from typing import Mapping, NamedTuple


class PgCommand(NamedTuple):
    args: list[str]
    env: dict[str, str]


def _db_url() -> str:
    return os.environ.get("DOCPILOT_DATABASE_URL", "postgresql://docpilot:docpilot123@localhost:5433/docpilot")


def _parse_pg_params(url: str) -> dict[str, str]:
    """Parse a postgresql:// URL into pg_dump/restore params."""
    url = url.replace("postgresql+psycopg://", "").replace("postgresql://", "")
    user_pass, host_db = url.split("@")
    user, password = user_pass.split(":")
    host_port, dbname = host_db.rsplit("/", 1)
    host, port = host_port.split(":") if ":" in host_port else (host_port, "5432")
    return {"host": host, "port": port, "dbname": dbname, "user": user, "password": password}


def build_backup_command(filepath: str, database_url: str | None = None, environ: Mapping[str, str] | None = None) -> PgCommand:
    params = _parse_pg_params(database_url or _db_url())
    env = {**dict(environ or os.environ), "PGPASSWORD": params["password"]}
    return PgCommand([
        "pg_dump",
        "-h", params["host"],
        "-p", params["port"],
        "-U", params["user"],
        "-d", params["dbname"],
        "--no-owner",
        "--no-privileges",
        "-f", filepath,
    ], env)


def build_restore_command(filepath: str, database_url: str | None = None, environ: Mapping[str, str] | None = None) -> PgCommand:
    params = _parse_pg_params(database_url or _db_url())
    env = {**dict(environ or os.environ), "PGPASSWORD": params["password"]}
    return PgCommand([
        "psql",
        "-h", params["host"],
        "-p", params["port"],
        "-U", params["user"],
        "-d", params["dbname"],
        "-f", filepath,
    ], env)


def backup(output_dir: str = "backups", dry_run: bool = False) -> str:
    """Create a pg_dump backup."""
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    filename = f"docpilot-{timestamp}.sql"
    filepath = os.path.join(output_dir, filename)

    command = build_backup_command(filepath)
    print(f"Running backup to {filepath}...")
    if dry_run:
        print(" ".join(command.args))
        return filepath
    result = subprocess.run(command.args, env=command.env, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Backup failed: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    print(f"Backup complete: {filepath}")
    return filepath


def restore(filepath: str, dry_run: bool = False) -> None:
    """Restore from a pg_dump backup."""
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}", file=sys.stderr)
        sys.exit(1)

    command = build_restore_command(filepath)
    print(f"Restoring from {filepath}...")
    if dry_run:
        print(" ".join(command.args))
        return
    result = subprocess.run(command.args, env=command.env, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Restore failed: {result.stderr}", file=sys.stderr)
        sys.exit(1)
    print("Restore complete.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Backup and restore DocPilot PostgreSQL database.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    backup_parser = subparsers.add_parser("backup")
    backup_parser.add_argument("--output-dir", default="backups")
    backup_parser.add_argument("--dry-run", action="store_true")
    restore_parser = subparsers.add_parser("restore")
    restore_parser.add_argument("filepath")
    restore_parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.command == "backup":
        backup(output_dir=args.output_dir, dry_run=args.dry_run)
        return 0
    restore(args.filepath, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
