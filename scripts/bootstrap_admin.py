#!/usr/bin/env python3
"""Provision or promote the first admin user for a DocPilot deployment.

Idempotent: re-running with the same email is safe.
Reads password from --password, the DOCPILOT_BOOTSTRAP_ADMIN_PASSWORD env var, or stdin.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Ensure the API package is importable when this script runs from the repo root.
_API_ROOT = Path(__file__).resolve().parents[1] / "services" / "api"
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

from app.auth.service import bootstrap_admin_command  # noqa: E402
from app.db import SessionLocal  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bootstrap or promote an admin user for DocPilot.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--display-name", required=True)
    parser.add_argument(
        "--password",
        default=None,
        help="Admin password. Falls back to DOCPILOT_BOOTSTRAP_ADMIN_PASSWORD or interactive prompt.",
    )
    parser.add_argument(
        "--promote",
        action="store_true",
        help="Promote an existing non-admin user with this email to admin.",
    )
    return parser.parse_args()


def _resolve_password(cli_value: str | None) -> str:
    if cli_value:
        return cli_value
    env_value = os.environ.get("DOCPILOT_BOOTSTRAP_ADMIN_PASSWORD")
    if env_value:
        return env_value
    import getpass

    return getpass.getpass("Admin password: ")


def main() -> int:
    args = parse_args()
    password = _resolve_password(args.password)
    if not password:
        print("error: password is required", file=sys.stderr)
        return 1

    db = SessionLocal()
    try:
        try:
            result = bootstrap_admin_command(
                db,
                email=args.email,
                display_name=args.display_name,
                password=password,
                promote=args.promote,
            )
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
    finally:
        db.close()

    print(f"{result.status}: {result.user.email} ({result.user.id})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
