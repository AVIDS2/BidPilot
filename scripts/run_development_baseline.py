"""Generate all BidPilot development-evaluation reports without provider calls."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
API_ROOT = REPO_ROOT / "services" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.evaluation.development_baseline import (  # noqa: E402
    build_development_baseline,
    write_development_baseline,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Write BidPilot's development-only evaluation baseline without provider calls."
    )
    parser.add_argument(
        "--benchmark-root",
        type=Path,
        default=REPO_ROOT / "benchmarks" / "bidbench" / "v1" / "demo-smart-community",
        help="directory containing the versioned development fixtures",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "output" / "development-evaluation",
        help="root directory for generated reports",
    )
    parser.add_argument(
        "--git-commit",
        help="commit recorded in the receipt; defaults to the current repository HEAD",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = build_development_baseline(
            args.benchmark_root,
            git_commit=args.git_commit or _current_git_commit(),
        )
        outputs = write_development_baseline(result, args.output_dir)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"development baseline failed: {exc}", file=sys.stderr)
        return 2

    print(f"Fixed cases: {result.receipt.total_case_count}")
    print("Release eligible: false (development control fixtures)")
    print(f"Baseline receipt: {outputs['baseline_json']}")
    return 0


def _current_git_commit() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    commit = result.stdout.strip()
    if not commit:
        raise ValueError("git rev-parse returned an empty commit")
    return commit


if __name__ == "__main__":
    raise SystemExit(main())
