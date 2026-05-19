import importlib.util
from pathlib import Path


_SCRIPT_PATH = Path(__file__).resolve().parents[3] / "scripts" / "release_rehearsal.py"
_SPEC = importlib.util.spec_from_file_location("release_rehearsal", _SCRIPT_PATH)
assert _SPEC is not None
release_rehearsal = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(release_rehearsal)


def test_build_steps_contains_core_release_gates() -> None:
    steps = release_rehearsal.build_steps(include_browser=False, include_load=False, include_production_readiness=False)

    names = [step.name for step in steps]
    commands = [step.command for step in steps]

    assert names == [
        "API migrations",
        "API tests",
        "Frontend typecheck",
        "Frontend unit tests",
        "Frontend build",
    ]
    assert "uv run --directory services/api alembic upgrade head" in commands
    assert "uv run --directory services/api pytest -q" in commands
    assert "pnpm --filter @docpilot/web exec tsc --noEmit" in commands
    assert "pnpm --filter @docpilot/web exec vitest run" in commands
    assert "pnpm --filter @docpilot/web run build" in commands


def test_build_steps_can_include_optional_release_gates() -> None:
    steps = release_rehearsal.build_steps(include_browser=True, include_load=True, include_production_readiness=True)

    names = [step.name for step in steps]

    assert "Playwright browser smoke" in names
    assert "API load smoke" in names
    assert "Production readiness gate" in names


def test_render_plan_marks_dry_run_commands() -> None:
    steps = [release_rehearsal.RehearsalStep(name="API tests", command="uv run --directory services/api pytest -q")]

    rendered = release_rehearsal.render_plan(steps)

    assert "Release rehearsal plan" in rendered
    assert "[dry-run] API tests" in rendered
    assert "uv run --directory services/api pytest -q" in rendered
