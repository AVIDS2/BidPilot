import importlib.util
from pathlib import Path


_SCRIPT_PATH = Path(__file__).resolve().parents[3] / "scripts" / "backup.py"
_SPEC = importlib.util.spec_from_file_location("backup_script", _SCRIPT_PATH)
assert _SPEC is not None
backup_script = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(backup_script)


def test_parse_pg_params_accepts_psycopg_sqlalchemy_url() -> None:
    params = backup_script._parse_pg_params("postgresql+psycopg://docpilot:secret@db.internal:5432/docpilot")

    assert params == {
        "host": "db.internal",
        "port": "5432",
        "dbname": "docpilot",
        "user": "docpilot",
        "password": "secret",
    }


def test_build_backup_command_uses_pg_dump_flags() -> None:
    command = backup_script.build_backup_command(
        "backup.sql",
        database_url="postgresql://docpilot:secret@db.internal:5432/docpilot",
        environ={},
    )

    assert command.env["PGPASSWORD"] == "secret"
    assert command.args == [
        "pg_dump",
        "-h",
        "db.internal",
        "-p",
        "5432",
        "-U",
        "docpilot",
        "-d",
        "docpilot",
        "--no-owner",
        "--no-privileges",
        "-f",
        "backup.sql",
    ]


def test_build_restore_command_uses_psql_file_restore() -> None:
    command = backup_script.build_restore_command(
        "backup.sql",
        database_url="postgresql://docpilot:secret@db.internal:5432/docpilot",
        environ={},
    )

    assert command.env["PGPASSWORD"] == "secret"
    assert command.args == [
        "psql",
        "-h",
        "db.internal",
        "-p",
        "5432",
        "-U",
        "docpilot",
        "-d",
        "docpilot",
        "-f",
        "backup.sql",
    ]
