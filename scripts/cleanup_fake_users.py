#!/usr/bin/env python3
"""Clean up fake test users from the database.

Detects fake users by email-domain patterns, then removes them and
all associated data (organisations, projects, bundles, etc.) while
respecting foreign-key constraints.

If a fake user shares an organisation with real (non-fake) users, only
the user row and its direct references (tokens, subscriptions, memberships)
are removed.  Otherwise the entire organisation subtree is purged.

Usage:
    python scripts/cleanup_fake_users.py [--dry-run] [--keep N]

    --dry-run   Report what would be deleted without actually deleting.
    --keep N    Keep the N most recent non-admin fake users (default 0).
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import ProgrammingError

# ---------------------------------------------------------------------------
# Ensure the API package is importable when running from the repo root.
# ---------------------------------------------------------------------------
_API_ROOT = Path(__file__).resolve().parents[1] / "services" / "api"
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

# ---------------------------------------------------------------------------
# Patterns used to identify fake / test users.
# These are matched case-insensitively against the user's email column.
# ---------------------------------------------------------------------------
FAKE_EMAIL_PATTERNS: list[str] = [
    "@example.com",
    "@test.com",
    "@test.local",
    "demo@docpilot",
    "test-user@",
    "deleted_",
    "@docpilot.ai",
]

# Well-known admin emails that should never be cleaned up (exact match).
PROTECTED_EMAILS: list[str] = [
    "admin@docpilot.ai",
]

# The default organisation UUID that ships with the schema -- we never
# delete this organisation even if all its users look "fake".
DEFAULT_ORG_ID = "00000000-0000-0000-0000-000000000001"

# ===================================================================
# Deletion steps for "fully fake" organisations (purge entire org).
#
# Each entry is (label, sql_statement).
# The order respects foreign-key constraints (leaf tables first).
# ===================================================================
# fmt: off
ORG_DELETION_STEPS: list[tuple[str, str]] = [
    # Direct user FK references
    ("refresh_token",       "DELETE FROM refresh_token WHERE user_id = ANY(:user_ids)"),
    ("subscription",        "DELETE FROM subscription WHERE user_id = ANY(:user_ids)"),
    ("team_member",         "DELETE FROM team_member WHERE user_id = ANY(:user_ids)"),
    ("invitation (by_user)","DELETE FROM invitation WHERE invited_by = ANY(:user_ids)"),
    ("invitation (org)",    "DELETE FROM invitation WHERE org_id = :org_id"),

    # Project-level tables (leaf FKs first)
    ("evidence",            "DELETE FROM evidence WHERE project_id = ANY(:project_ids)"),
    ("review_comment",
     "DELETE FROM review_comment WHERE review_thread_id IN ("
     "  SELECT id FROM review_thread WHERE deliverable_section_id IN ("
     "    SELECT id FROM deliverable_section WHERE deliverable_id IN ("
     "      SELECT id FROM deliverable WHERE project_id = ANY(:project_ids)"
     "    )"
     "  )"
     ")"),
    ("knowledge_chunk",     "DELETE FROM knowledge_chunk WHERE project_id = ANY(:project_ids)"),
    ("section_version",
     "DELETE FROM section_version WHERE deliverable_section_id IN ("
     "  SELECT id FROM deliverable_section WHERE deliverable_id IN ("
     "    SELECT id FROM deliverable WHERE project_id = ANY(:project_ids)"
     "  )"
     ")"),
    ("review_thread",
     "DELETE FROM review_thread WHERE deliverable_section_id IN ("
     "  SELECT id FROM deliverable_section WHERE deliverable_id IN ("
     "    SELECT id FROM deliverable WHERE project_id = ANY(:project_ids)"
     "  )"
     ")"),
    ("execution_run",       "DELETE FROM execution_run WHERE project_id = ANY(:project_ids)"),
    ("requirement_item",    "DELETE FROM requirement_item WHERE project_id = ANY(:project_ids)"),
    ("parsed_asset",
     "DELETE FROM parsed_asset WHERE source_document_id IN ("
     "  SELECT id FROM source_document WHERE bundle_id IN ("
     "    SELECT id FROM bundle WHERE project_id = ANY(:project_ids)"
     "  )"
     ")"),
    ("source_document",
     "DELETE FROM source_document WHERE bundle_id IN ("
     "  SELECT id FROM bundle WHERE project_id = ANY(:project_ids)"
     ")"),
    ("deliverable_section",
     "DELETE FROM deliverable_section WHERE deliverable_id IN ("
     "  SELECT id FROM deliverable WHERE project_id = ANY(:project_ids)"
     ")"),
    ("deliverable",         "DELETE FROM deliverable WHERE project_id = ANY(:project_ids)"),
    ("bundle",              "DELETE FROM bundle WHERE project_id = ANY(:project_ids)"),
    ("audit_event",         "DELETE FROM audit_event WHERE project_id = ANY(:project_ids)"),

    # Org-level tables
    ("project",             "DELETE FROM project WHERE org_id = :org_id"),
    ("team",                "DELETE FROM team WHERE org_id = :org_id"),

    # Finally the user and organisation rows
    ("user",                "DELETE FROM \"user\" WHERE id = ANY(:user_ids)"),
    ("organization",        "DELETE FROM organization WHERE id = :org_id"),
]
# fmt: on

# ===================================================================
# Deletion steps for "mixed" orgs (user-level removal only).
# ===================================================================
# fmt: off
USER_DELETION_STEPS: list[tuple[str, str]] = [
    ("refresh_token",           "DELETE FROM refresh_token WHERE user_id = ANY(:user_ids)"),
    ("subscription",            "DELETE FROM subscription WHERE user_id = ANY(:user_ids)"),
    ("team_member",             "DELETE FROM team_member WHERE user_id = ANY(:user_ids)"),
    ("invitation",              "DELETE FROM invitation WHERE invited_by = ANY(:user_ids)"),
    # Non-FK string references -- safe to clean up without FK trouble.
    ("audit_event (actor)",     "DELETE FROM audit_event WHERE actor_id = ANY(:user_ids)"),
    ("review_thread (opener)",  "DELETE FROM review_thread WHERE opened_by = ANY(:user_ids)"),
    ("review_thread (resolver)","DELETE FROM review_thread WHERE resolved_by = ANY(:user_ids)"),
    ("review_comment (author)", "DELETE FROM review_comment WHERE author_id = ANY(:user_ids)"),
    ("user",                    "DELETE FROM \"user\" WHERE id = ANY(:user_ids)"),
]
# fmt: on

# ===================================================================
# Helper utilities
# ===================================================================


def _get_db_url() -> str:
    """Return the database URL from the environment or the dev default."""
    return os.environ.get(
        "DOCPILOT_DATABASE_URL",
        "postgresql+psycopg://docpilot:docpilot@localhost:5433/docpilot",
    )


def _table_exists(conn: Connection, table_name: str) -> bool:
    """Return True if *table_name* exists in the public schema."""
    try:
        result = conn.execute(
            text(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name = :name"
            ),
            {"name": table_name},
        )
        return result.scalar() is not None
    except Exception:
        return False


def _execute_stmt(
    conn: Connection,
    label: str,
    sql: str,
    params: dict[str, Any],
) -> int:
    """Execute *sql* (DELETE or SELECT COUNT), returning affected rows.

    Gracefully skips statements whose target table does not exist
    (returns 0 and prints a warning).
    """
    try:
        result = conn.execute(text(sql), params)
        # rowcount is -1 for SELECT, actual count for DELETE.
        return result.rowcount if result.rowcount != -1 else (result.scalar() or 0)
    except ProgrammingError as exc:
        exc_msg = str(exc).lower()
        if "does not exist" in exc_msg or "relation " in exc_msg:
            print(f"  [SKIP] Table not found for '{label}': {exc}", file=sys.stderr)
            return 0
        raise


# ===================================================================
# Query helpers
# ===================================================================


def _find_fake_users(
    conn: Connection,
    keep: int = 0,
) -> list[dict[str, Any]]:
    """Query for non-admin users matching fake email patterns.

    Returns a list of dicts ordered by *created_at* descending.
    If *keep* > 0, the *keep* most-recent users are excluded.
    """
    conditions: list[str] = []
    params: dict[str, str] = {}
    for i, pat in enumerate(FAKE_EMAIL_PATTERNS):
        key = f"p{i}"
        conditions.append(f"u.email ILIKE :{key}")
        params[key] = f"%{pat}%"

    where_clause = " OR ".join(conditions)

    sql = text(
        f"""
        SELECT
            u.id,
            u.email,
            u.display_name,
            u.org_id,
            u.role,
            u.created_at,
            o.slug AS org_slug,
            o.name AS org_name
        FROM "user" u
        JOIN organization o ON o.id = u.org_id
        WHERE ({where_clause})
          AND u.role != 'admin'
        ORDER BY u.created_at DESC
        """
    )

    rows = conn.execute(sql, params).fetchall()

    all_users = [
        {
            "id": r[0],
            "email": r[1],
            "display_name": r[2],
            "org_id": r[3],
            "role": r[4],
            "created_at": r[5],
            "org_slug": r[6],
            "org_name": r[7],
        }
        for r in rows
        if r[1] not in PROTECTED_EMAILS
    ]

    if keep > 0 and len(all_users) > keep:
        return all_users[keep:]
    elif keep > 0:
        return []
    return all_users


def _org_user_counts(
    conn: Connection,
    org_ids: list[str],
) -> dict[str, int]:
    """Return a dict mapping org_id -> total number of users in that org."""
    if not org_ids:
        return {}
    sql = text(
        "SELECT org_id, COUNT(*) AS cnt FROM \"user\" "
        "WHERE org_id = ANY(:oids) GROUP BY org_id"
    )
    rows = conn.execute(sql, {"oids": org_ids}).fetchall()
    return {r[0]: r[1] for r in rows}


def _project_ids_for_org(
    conn: Connection,
    org_id: str,
) -> list[str]:
    """Return all project IDs belonging to *org_id*."""
    sql = text("SELECT id FROM project WHERE org_id = :oid")
    rows = conn.execute(sql, {"oid": org_id}).fetchall()
    return [r[0] for r in rows]


def _classify_orgs(
    conn: Connection,
    fake_users: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split *fake_users* into ``fully_fake`` and ``mixed`` org buckets.

    *fully_fake* -- users whose organisation contains **only** fake users
    (and the org is not the built-in default org).
    *mixed* -- users whose organisation also contains real (non-fake) users,
    or users in the default org.
    """
    fake_per_org: dict[str, list[dict]] = {}
    for u in fake_users:
        fake_per_org.setdefault(u["org_id"], []).append(u)

    total_counts = _org_user_counts(conn, list(fake_per_org.keys()))

    fully_fake: list[dict] = []
    mixed: list[dict] = []
    for oid, members in fake_per_org.items():
        total = total_counts.get(oid, 0)
        if total == len(members) and oid != DEFAULT_ORG_ID:
            fully_fake.extend(members)
        else:
            mixed.extend(members)

    return fully_fake, mixed


# ===================================================================
# Count simulation (SELECT COUNT) -- no actual deletes.
# ===================================================================


def _simulate_counts(
    conn: Connection,
    fully_fake: list[dict[str, Any]],
    mixed: list[dict[str, Any]],
) -> dict[str, int]:
    """Run SELECT COUNT equivalents to estimate rows that would be deleted.

    This is safe -- no DML is executed.
    """
    total: dict[str, int] = {}

    # -- Fully-fake orgs --
    by_org: dict[str, list[dict]] = defaultdict(list)
    for u in fully_fake:
        by_org[u["org_id"]].append(u)

    for org_id, members in by_org.items():
        user_ids = [m["id"] for m in members]
        project_ids = _project_ids_for_org(conn, org_id)

        for label, sql_del in ORG_DELETION_STEPS:
            params: dict[str, Any] = {}
            if ":user_ids" in sql_del:
                params["user_ids"] = user_ids
            if ":project_ids" in sql_del:
                params["project_ids"] = project_ids
            if ":org_id" in sql_del:
                params["org_id"] = org_id

            # Rewrite DELETE as SELECT COUNT for safety.
            count_sql = sql_del.replace("DELETE FROM", "SELECT COUNT(*) FROM", 1)
            n = _execute_stmt(conn, label, count_sql, params)
            total[label] = total.get(label, 0) + n

    # -- Mixed orgs --
    if mixed:
        user_ids = [u["id"] for u in mixed]
        for label, sql_del in USER_DELETION_STEPS:
            params = {"user_ids": user_ids}
            count_sql = sql_del.replace("DELETE FROM", "SELECT COUNT(*) FROM", 1)
            n = _execute_stmt(conn, label, count_sql, params)
            total[label] = total.get(label, 0) + n

    return total


# ===================================================================
# Actual deletion execution.
# ===================================================================


def _execute_deletions(
    conn: Connection,
    fully_fake: list[dict[str, Any]],
    mixed: list[dict[str, Any]],
) -> dict[str, int]:
    """Execute all DELETE statements, tracking per-table counts."""
    total: dict[str, int] = {}

    # -- Fully-fake orgs --
    by_org: dict[str, list[dict]] = defaultdict(list)
    for u in fully_fake:
        by_org[u["org_id"]].append(u)

    for org_id, members in by_org.items():
        user_ids = [m["id"] for m in members]
        project_ids = _project_ids_for_org(conn, org_id)

        for label, sql_del in ORG_DELETION_STEPS:
            params: dict[str, Any] = {}
            if ":user_ids" in sql_del:
                params["user_ids"] = user_ids
            if ":project_ids" in sql_del:
                params["project_ids"] = project_ids
            if ":org_id" in sql_del:
                params["org_id"] = org_id
            n = _execute_stmt(conn, label, sql_del, params)
            total[label] = total.get(label, 0) + n

    # -- Mixed orgs --
    if mixed:
        user_ids = [u["id"] for u in mixed]
        for label, sql_del in USER_DELETION_STEPS:
            params = {"user_ids": user_ids}
            n = _execute_stmt(conn, label, sql_del, params)
            total[label] = total.get(label, 0) + n

    return total


# ===================================================================
# Report formatting
# ===================================================================


def _print_counts(total_counts: dict[str, int]) -> None:
    """Print per-table row counts sorted by label."""
    if not total_counts:
        print("  (no rows to delete)")
        return
    total_rows = 0
    for table, count in sorted(total_counts.items()):
        if count > 0:
            print(f"    {table}: {count:,}")
            total_rows += count
    print(f"    {'─' * 40}")
    print(f"    TOTAL: {total_rows:,} rows")


def _print_report(
    fully_fake: list[dict[str, Any]],
    mixed: list[dict[str, Any]],
    total_counts: dict[str, int],
    dry_run: bool,
) -> None:
    """Print a human-readable summary of what was / would be deleted."""
    prefix = "[DRY RUN] " if dry_run else ""
    all_users = fully_fake + mixed

    if not all_users:
        print(f"{prefix}No fake users found.")
        return

    print()
    print(f"{prefix}{'=' * 72}")
    print(f"{prefix}  Fake users found: {len(all_users)}")
    print(f"{prefix}{'=' * 72}")
    print()
    print(f"{prefix}{'ID':36s} {'Email':40s} {'Role':12s} {'Org':20s} {'Created'}")
    print(f"{prefix}{'-' * 110}")
    for u in all_users:
        print(
            f"{prefix}  {u['id']:36s} {u['email']:40s} {u['role']:12s} "
            f"{u['org_slug']:20s} {str(u['created_at']):19s}"
        )

    print()
    if fully_fake:
        fake_org_ids = sorted({u["org_id"] for u in fully_fake})
        print(
            f"{prefix}{len(fully_fake)} user(s) in {len(fake_org_ids)} "
            f"fully-fake org(s) -- entire org(s) will be deleted."
        )
    if mixed:
        mixed_org_ids = sorted({u["org_id"] for u in mixed})
        print(
            f"{prefix}{len(mixed)} user(s) in {len(mixed_org_ids)} org(s) "
            f"with mixed/real users -- only user rows will be removed."
        )

    print(f"\n{prefix}Rows to delete:")
    _print_counts(total_counts)
    print()


# ===================================================================
# Main
# ===================================================================


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Clean up fake test users from the database.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be deleted without actually deleting.",
    )
    parser.add_argument(
        "--keep",
        type=int,
        default=0,
        help="Keep the N most recent non-admin fake users (default 0).",
    )
    args = parser.parse_args()

    # ------------------------------------------------------------------
    # Connect & verify
    # ------------------------------------------------------------------
    database_url = _get_db_url()
    engine = create_engine(database_url, pool_pre_ping=True)

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        print(f"ERROR: Could not connect to the database:\n  {exc}", file=sys.stderr)
        return 1

    # ------------------------------------------------------------------
    # Phase 1: Find & classify fake users
    # ------------------------------------------------------------------
    print("Scanning for fake users ...")

    with engine.connect() as conn:
        # Verify basic schema sanity.
        if not _table_exists(conn, "user"):
            print(
                "ERROR: The 'user' table does not exist in the target database.",
                file=sys.stderr,
            )
            return 1

        fake_users = _find_fake_users(conn, keep=args.keep)

        if not fake_users:
            print("No fake users found. Nothing to do.")
            return 0

        fully_fake, mixed = _classify_orgs(conn, fake_users)

        print(f"  Total fake users found:  {len(fake_users)}")
        print(f"  Fully-fake org(s):       {len(fully_fake)} user(s)")
        print(f"  Mixed / default org(s):  {len(mixed)} user(s)")
        print()

        # ------------------------------------------------------------------
        # Phase 2: Simulate counts (SELECT COUNT, not DELETE)
        # ------------------------------------------------------------------
        print("Simulating deletion counts ...")
        total_counts = _simulate_counts(conn, fully_fake, mixed)

    # Print report.
    _print_report(fully_fake, mixed, total_counts, dry_run=args.dry_run)

    if args.dry_run:
        print("[DRY RUN] No changes were made.")
        return 0

    # ------------------------------------------------------------------
    # Phase 3: Confirm
    # ------------------------------------------------------------------
    all_users = fully_fake + mixed
    confirm = input(
        f"Delete {len(all_users)} user(s) and all associated data? "
        f"(type 'yes' to confirm): "
    )
    if confirm.strip().lower() != "yes":
        print("Aborted.")
        return 0

    # ------------------------------------------------------------------
    # Phase 4: Execute deletions (in a single transaction)
    # ------------------------------------------------------------------
    print("\nDeleting ...")
    with engine.begin() as conn:
        final_counts = _execute_deletions(conn, fully_fake, mixed)
        # engine.begin() commits on success, rolls back on exception.

    print(f"\nDone. Deleted {len(all_users)} user(s).")
    print("Rows deleted by table:")
    _print_counts(final_counts)

    return 0


# ===================================================================

if __name__ == "__main__":
    raise SystemExit(main())
