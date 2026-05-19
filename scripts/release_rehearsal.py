from __future__ import annotations

import argparse
import subprocess
import sys
from typing import NamedTuple


class RehearsalStep(NamedTuple):
    name: str
    command: str


def build_steps(
    include_browser: bool,
    include_load: bool,
    include_production_readiness: bool,
) -> list[RehearsalStep]:
    steps = [
        RehearsalStep("API migrations", "uv run --directory services/api alembic upgrade head"),
        RehearsalStep("API tests", "uv run --directory services/api pytest -q"),
        RehearsalStep("Frontend typecheck", "pnpm --filter @docpilot/web exec tsc --noEmit"),
        RehearsalStep("Frontend unit tests", "pnpm --filter @docpilot/web exec vitest run"),
        RehearsalStep("Frontend build", "pnpm --filter @docpilot/web run build"),
    ]

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


def render_plan(steps: list[RehearsalStep]) -> str:
    lines = ["Release rehearsal plan"]
    for index, step in enumerate(steps, start=1):
        lines.append(f"{index}. [dry-run] {step.name}")
        lines.append(f"   {step.command}")
    return "\n".join(lines)


def run_steps(steps: list[RehearsalStep]) -> int:
    for step in steps:
        print(f"\n==> {step.name}")
        print(step.command)
        completed = subprocess.run(step.command, shell=True)
        if completed.returncode != 0:
            print(f"failed: {step.name}", file=sys.stderr)
            return completed.returncode
    print("\nrelease rehearsal passed")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run or print the DocPilot release rehearsal gate sequence.")
    parser.add_argument("--run", action="store_true", help="execute the rehearsal steps instead of printing the dry-run plan")
    parser.add_argument("--include-browser", action="store_true", help="include Playwright browser smoke tests")
    parser.add_argument("--include-load", action="store_true", help="include API load smoke; requires the API to be running locally")
    parser.add_argument("--include-production-readiness", action="store_true", help="include production readiness; requires production-shaped env vars")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    steps = build_steps(
        include_browser=args.include_browser,
        include_load=args.include_load,
        include_production_readiness=args.include_production_readiness,
    )
    if not args.run:
        print(render_plan(steps))
        return 0
    return run_steps(steps)


if __name__ == "__main__":
    raise SystemExit(main())
