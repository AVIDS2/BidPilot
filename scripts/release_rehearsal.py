from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path, PureWindowsPath
from typing import NamedTuple


_SCRIPT_DIR = Path(__file__).resolve().parent
_REPOSITORY_ROOT = _SCRIPT_DIR.parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from test_database_safety import UnsafeTestDatabaseError, build_test_environment  # noqa: E402


class RehearsalStep(NamedTuple):
    name: str
    command: str


class RehearsalStepResult(NamedTuple):
    name: str
    command: str
    returncode: int
    duration_ms: float


class RehearsalResult(NamedTuple):
    started_at: str
    completed_at: str
    steps: tuple[RehearsalStepResult, ...]

    @property
    def passed(self) -> bool:
        return bool(self.steps) and all(step.returncode == 0 for step in self.steps)

    @property
    def failed_step(self) -> str | None:
        return next((step.name for step in self.steps if step.returncode != 0), None)

    @property
    def returncode(self) -> int:
        return next((step.returncode for step in self.steps if step.returncode != 0), 0)


def build_steps(
    include_browser: bool,
    include_load: bool,
    include_production_readiness: bool,
    quality_gate_command: str | None = None,
) -> list[RehearsalStep]:
    steps = [
        RehearsalStep("API migrations", "uv run --directory services/api --locked --no-sync alembic upgrade head"),
        RehearsalStep("API static checks", "uv run --directory services/api --locked --no-sync ruff check app tests"),
        RehearsalStep("API tests", "uv run --directory services/api --locked --no-sync pytest -q"),
        RehearsalStep("Worker static checks", "uv run --directory services/worker --locked --no-sync ruff check app tests"),
        RehearsalStep("Worker tests", "uv run --directory services/worker --locked --no-sync pytest -q"),
        RehearsalStep("Frontend typecheck", "pnpm --filter @docpilot/web exec tsc --noEmit"),
        RehearsalStep("Frontend unit tests", "pnpm --filter @docpilot/web exec vitest run"),
        RehearsalStep("Frontend build", "pnpm --filter @docpilot/web run build"),
    ]

    if quality_gate_command:
        steps.append(RehearsalStep("Agent quality gate", quality_gate_command))
    if include_browser:
        steps.append(
            RehearsalStep(
                "Playwright browser smoke",
                'pnpm --dir apps/web exec playwright test --project=chromium --grep-invert "@demo"',
            )
        )
    if include_load:
        steps.append(
            RehearsalStep(
                "API load smoke",
                "python scripts/load_smoke.py --base-url http://127.0.0.1:8000 --requests 20 --concurrency 4 --max-error-rate 0 --max-p95-ms 1000",
            )
        )
    if include_production_readiness:
        steps.append(
            RehearsalStep(
                "Production readiness gate",
                "python scripts/production_readiness.py --target production",
            )
        )
    return steps


def build_quality_gate_command(
    *,
    policy: Path,
    bidbench_report: Path,
    retrieval_report: Path,
    memory_report: Path,
    assistant_report: Path,
    expected_git_commit: str,
) -> str:
    """Return a shell-safe release-mode quality gate command."""
    arguments = [
        "uv",
        "run",
        "--locked",
        "--no-sync",
        "python",
        "scripts/run_quality_gate.py",
        "--policy",
        str(policy),
        "--bidbench-report",
        str(bidbench_report),
        "--retrieval-report",
        str(retrieval_report),
        "--memory-report",
        str(memory_report),
        "--assistant-report",
        str(assistant_report),
        "--mode",
        "release",
        "--expected-git-commit",
        expected_git_commit,
    ]
    return shlex.join(arguments)


def render_plan(steps: list[RehearsalStep]) -> str:
    lines = ["Release rehearsal plan"]
    for index, step in enumerate(steps, start=1):
        lines.append(f"{index}. [dry-run] {step.name}")
        lines.append(f"   {step.command}")
    return "\n".join(lines)


def run_steps(
    steps: list[RehearsalStep],
    *,
    environment: dict[str, str] | None = None,
    working_directory: Path | None = None,
) -> RehearsalResult:
    started_at = datetime.now(UTC).isoformat()
    results: list[RehearsalStepResult] = []
    for step in steps:
        print(f"\n==> {step.name}")
        print(step.command)
        started = time.perf_counter()
        completed = subprocess.run(
            step.command,
            shell=True,
            env=environment,
            cwd=working_directory,
        )
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        results.append(
            RehearsalStepResult(
                name=step.name,
                command=step.command,
                returncode=completed.returncode,
                duration_ms=duration_ms,
            )
        )
        if completed.returncode != 0:
            print(f"failed: {step.name}", file=sys.stderr)
            break

    result = RehearsalResult(
        started_at=started_at,
        completed_at=datetime.now(UTC).isoformat(),
        steps=tuple(results),
    )
    if result.passed:
        print("\nrelease rehearsal passed")
    else:
        print("\nrelease rehearsal failed", file=sys.stderr)
    return result


def build_evidence_artifact(
    result: RehearsalResult,
    *,
    git_commit: str | None,
    git_dirty: bool | None,
) -> dict[str, object]:
    """Return a redacted source-rehearsal record with no env or command output."""

    return {
        "schema_version": "1.0",
        "kind": "source_release_rehearsal",
        "generated_at": result.completed_at,
        "started_at": result.started_at,
        "git": {
            "commit": git_commit,
            "tracked_worktree_dirty": git_dirty,
        },
        "test_environment": {"database": "dedicated_test_database"},
        "steps": [
            {
                "name": step.name,
                "returncode": step.returncode,
                "duration_ms": step.duration_ms,
            }
            for step in result.steps
        ],
        "failed_step": result.failed_step,
        "passed": result.passed,
    }


def write_evidence_artifact(artifact: dict[str, object], output_file: Path) -> Path:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return output_file


def resolve_evidence_output_file(output_file: Path) -> Path:
    if output_file.is_absolute() or PureWindowsPath(output_file).is_absolute():
        return output_file
    return _REPOSITORY_ROOT / output_file


def read_git_metadata() -> tuple[str | None, bool | None]:
    """Collect safe repository metadata without retaining paths or shell output."""

    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            check=True,
            text=True,
        ).stdout.strip()
        tracked_worktree_dirty = any(
            subprocess.run(
                command,
                capture_output=True,
                check=False,
            ).returncode
            != 0
            for command in (
                ["git", "diff", "--quiet"],
                ["git", "diff", "--cached", "--quiet"],
            )
        )
        return commit or None, tracked_worktree_dirty
    except (OSError, subprocess.SubprocessError):
        return None, None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run or print the DocPilot release rehearsal gate sequence.")
    parser.add_argument("--run", action="store_true", help="execute the rehearsal steps instead of printing the dry-run plan")
    parser.add_argument("--include-browser", action="store_true", help="include Playwright browser smoke tests")
    parser.add_argument("--include-load", action="store_true", help="include API load smoke; requires the API to be running locally")
    parser.add_argument("--include-production-readiness", action="store_true", help="include production readiness; requires production-shaped env vars")
    parser.add_argument("--include-quality-gate", action="store_true", help="include the captured Agent quality gate")
    parser.add_argument("--quality-gate-policy", type=Path)
    parser.add_argument("--bidbench-report", type=Path)
    parser.add_argument("--retrieval-report", type=Path)
    parser.add_argument("--memory-report", type=Path)
    parser.add_argument("--assistant-report", type=Path)
    parser.add_argument("--quality-gate-git-commit")
    parser.add_argument(
        "--output-file",
        type=Path,
        help="write a redacted JSON source-release evidence artifact after --run",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        quality_gate_command = _quality_gate_command_from_args(args)
    except ValueError as exc:
        print(f"invalid quality-gate arguments: {exc}", file=sys.stderr)
        return 2
    steps = build_steps(
        include_browser=args.include_browser,
        include_load=args.include_load,
        include_production_readiness=args.include_production_readiness,
        quality_gate_command=quality_gate_command,
    )
    if not args.run:
        if args.output_file is not None:
            print("--output-file requires --run", file=sys.stderr)
            return 2
        print(render_plan(steps))
        return 0
    try:
        test_environment = build_test_environment(os.environ)
    except UnsafeTestDatabaseError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    result = run_steps(
        steps,
        environment=test_environment,
        working_directory=_REPOSITORY_ROOT,
    )
    if args.output_file is not None:
        git_commit, git_dirty = read_git_metadata()
        artifact_path = write_evidence_artifact(
            build_evidence_artifact(
                result,
                git_commit=git_commit,
                git_dirty=git_dirty,
            ),
            resolve_evidence_output_file(args.output_file),
        )
        print(f"evidence_artifact={artifact_path}")
    return result.returncode


def _quality_gate_command_from_args(args: argparse.Namespace) -> str | None:
    if not args.include_quality_gate:
        return None

    required_values = {
        "--quality-gate-policy": args.quality_gate_policy,
        "--bidbench-report": args.bidbench_report,
        "--retrieval-report": args.retrieval_report,
        "--memory-report": args.memory_report,
        "--assistant-report": args.assistant_report,
        "--quality-gate-git-commit": args.quality_gate_git_commit,
    }
    missing = [name for name, value in required_values.items() if not value]
    if missing:
        raise ValueError(f"--include-quality-gate requires {', '.join(missing)}")

    return build_quality_gate_command(
        policy=args.quality_gate_policy,
        bidbench_report=args.bidbench_report,
        retrieval_report=args.retrieval_report,
        memory_report=args.memory_report,
        assistant_report=args.assistant_report,
        expected_git_commit=args.quality_gate_git_commit,
    )


if __name__ == "__main__":
    raise SystemExit(main())
