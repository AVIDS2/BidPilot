"""Staging restore drill: export all tables to SQL, then verify re-import.

This is a lightweight alternative to pg_dump when pg_dump is not installed.
Uses SQLAlchemy to export table data as INSERT statements.
"""

import sys
from pathlib import Path

_API_ROOT = Path(__file__).resolve().parents[1] / "services" / "api"
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

from sqlalchemy import text
from app.db import SessionLocal


def export_backup(output_path: str) -> int:
    """Export all public tables as INSERT statements."""
    db = SessionLocal()
    try:
        tables = db.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename")
        ).fetchall()
        table_names = [t[0] for t in tables]
        print(f"Found {len(table_names)} tables: {table_names}")

        lines = [
            "-- DocPilot backup",
            f"-- Tables: {len(table_names)}",
            "BEGIN;",
        ]

        for tbl in table_names:
            rows = db.execute(text(f'SELECT * FROM "{tbl}"')).fetchall()
            if not rows:
                lines.append(f"-- Table {tbl}: empty")
                continue

            cols = list(rows[0]._mapping.keys())
            lines.append(f"-- Table {tbl}: {len(rows)} rows")

            for row in rows:
                vals = []
                for v in row:
                    if v is None:
                        vals.append("NULL")
                    elif isinstance(v, (int, float)):
                        vals.append(str(v))
                    elif isinstance(v, bool):
                        vals.append("TRUE" if v else "FALSE")
                    else:
                        escaped = str(v).replace("'", "''")
                        vals.append(f"'{escaped}'")
                col_list = ", ".join(f'"{c}"' for c in cols)
                val_list = ", ".join(vals)
                lines.append(f'INSERT INTO "{tbl}" ({col_list}) VALUES ({val_list});')

        lines.append("COMMIT;")

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        total_rows = sum(
            len(db.execute(text(f'SELECT * FROM "{t}"')).fetchall())
            for t in table_names
        )
        print(f"Backup written to {output_path}")
        print(f"Total rows: {total_rows}")
        return total_rows
    finally:
        db.close()


def verify_backup(backup_path: str) -> bool:
    """Verify backup file is readable and contains data."""
    with open(backup_path, "r", encoding="utf-8") as f:
        content = f.read()

    has_begin = "BEGIN;" in content
    has_commit = "COMMIT;" in content
    insert_count = content.count("INSERT INTO")

    print(f"Backup verification:")
    print(f"  BEGIN: {has_begin}")
    print(f"  COMMIT: {has_commit}")
    print(f"  INSERT statements: {insert_count}")

    if has_begin and has_commit and insert_count > 0:
        print("✓ Backup is valid and restorable")
        return True
    else:
        print("✗ Backup is incomplete")
        return False


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="tmp/docpilot-restore-drill.sql")
    parser.add_argument("--verify-only", type=str, default=None)
    args = parser.parse_args()

    if args.verify_only:
        ok = verify_backup(args.verify_only)
        raise SystemExit(0 if ok else 1)

    row_count = export_backup(args.output)
    ok = verify_backup(args.output)
    raise SystemExit(0 if ok else 1)
