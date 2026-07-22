import importlib.util
import json
from pathlib import Path

import pytest


_SCRIPT_PATH = Path(__file__).resolve().parents[3] / "scripts" / "release_rehearsal.py"
_SPEC = importlib.util.spec_from_file_location("release_rehearsal", _SCRIPT_PATH)
assert _SPEC is not None
release_rehearsal = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(release_rehearsal)


@pytest.fixture(autouse=True)
def reset_usage_events() -> None:
    """The release-plan builder is intentionally independent from PostgreSQL."""
    yield


def test_build_steps_contains_core_release_gates() -> None:
    steps = release_rehearsal.build_steps(include_browser=False, include_load=False, include_production_readiness=False)

    names = [step.name for step in steps]
    commands = [step.command for step in steps]

    assert names == [
        "API migrations",
        "API static checks",
        "API tests",
        "Worker static checks",
        "Worker tests",
        "Frontend typecheck",
        "Frontend unit tests",
        "Frontend build",
    ]
    assert "uv run --directory services/api alembic upgrade head" in commands
    assert "uv run --directory services/api ruff check app tests" in commands
    assert "uv run --directory services/api pytest -q" in commands
    assert "uv run --directory services/worker ruff check app tests" in commands
    assert "uv run --directory services/worker pytest -q" in commands
    assert "pnpm --filter @docpilot/web exec tsc --noEmit" in commands
    assert "pnpm --filter @docpilot/web exec vitest run" in commands
    assert "pnpm --filter @docpilot/web run build" in commands


def test_build_steps_can_include_optional_release_gates() -> None:
    steps = release_rehearsal.build_steps(include_browser=True, include_load=True, include_production_readiness=True)

    names = [step.name for step in steps]

    assert "Playwright browser smoke" in names
    assert "API load smoke" in names
    assert "Production readiness gate" in names


def test_build_steps_can_include_the_quality_gate_with_captured_reports() -> None:
    command = (
        "uv run python scripts/run_quality_gate.py --policy release-policy.json "
        "--bidbench-report bidbench.json --retrieval-report retrieval.json "
        "--memory-report memory.json --assistant-report assistant.json "
        "--mode release --expected-git-commit abc123"
    )
    steps = release_rehearsal.build_steps(
        include_browser=False,
        include_load=False,
        include_production_readiness=False,
        quality_gate_command=command,
    )

    quality_step = next(step for step in steps if step.name == "Agent quality gate")

    assert quality_step.command == command


def test_render_plan_marks_dry_run_commands() -> None:
    steps = [release_rehearsal.RehearsalStep(name="API tests", command="uv run --directory services/api pytest -q")]

    rendered = release_rehearsal.render_plan(steps)

    assert "Release rehearsal plan" in rendered
    assert "[dry-run] API tests" in rendered
    assert "uv run --directory services/api pytest -q" in rendered


def test_release_rehearsal_test_environment_requires_dedicated_database() -> None:
    with pytest.raises(release_rehearsal.UnsafeTestDatabaseError):
        release_rehearsal.build_test_environment(
            {"DOCPILOT_DATABASE_URL": "postgresql://app:secret@localhost/docpilot"}
        )


def test_rehearsal_evidence_is_redacted_and_records_each_gate(tmp_path: Path) -> None:
    result = release_rehearsal.RehearsalResult(
        started_at="2026-07-22T00:00:00+00:00",
        completed_at="2026-07-22T00:00:12+00:00",
        steps=(
            release_rehearsal.RehearsalStepResult(
                name="API tests",
                command="uv run --directory services/api pytest -q",
                returncode=0,
                duration_ms=12.5,
            ),
            release_rehearsal.RehearsalStepResult(
                name="Frontend build",
                command="pnpm --filter @docpilot/web run build",
                returncode=1,
                duration_ms=42.25,
            ),
        ),
    )

    artifact = release_rehearsal.build_evidence_artifact(
        result,
        git_commit="abc123",
        git_dirty=True,
    )
    output_file = release_rehearsal.write_evidence_artifact(
        artifact,
        tmp_path / "release-evidence" / "source-rehearsal.json",
    )

    saved = json.loads(output_file.read_text(encoding="utf-8"))
    assert saved["kind"] == "source_release_rehearsal"
    assert saved["passed"] is False
    assert saved["failed_step"] == "Frontend build"
    assert saved["git"] == {"commit": "abc123", "tracked_worktree_dirty": True}
    assert saved["steps"][0]["duration_ms"] == 12.5
    contents = output_file.read_text(encoding="utf-8")
    assert "postgresql" not in contents
    assert "secret" not in contents
