from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
API_ROOT = REPO_ROOT / "services" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.evaluation.adapters import build_candidate_from_requirement_snapshot  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert a saved BidPilot /requirements response into a BidBench candidate."
    )
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument("--candidate-id", required=True)
    parser.add_argument("--git-commit")
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    candidate = build_candidate_from_requirement_snapshot(
        snapshot_path=args.snapshot,
        dataset_id=args.dataset_id,
        candidate_id=args.candidate_id,
        git_commit=args.git_commit,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(candidate.model_dump_json(indent=2), encoding="utf-8")
    print(f"Candidate written: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
