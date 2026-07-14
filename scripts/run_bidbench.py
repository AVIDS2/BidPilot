from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
API_ROOT = REPO_ROOT / "services" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.evaluation.bidbench import (  # noqa: E402
    BidBenchThresholds,
    check_thresholds,
    evaluate_files,
    write_report,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Score a saved BidBench candidate without calling a model provider."
    )
    parser.add_argument("--dataset", type=Path, required=True, help="dataset directory or dataset.json")
    parser.add_argument("--candidate", type=Path, required=True, help="saved candidate JSON")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "output" / "bidbench",
        help="report output directory (default: output/bidbench)",
    )
    parser.add_argument("--min-mandatory-recall", type=float)
    parser.add_argument("--min-scored-recall", type=float)
    parser.add_argument("--min-source-association-accuracy", type=float)
    parser.add_argument("--min-combined-score", type=float)
    parser.add_argument("--max-unsupported-claim-rate", type=float)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = evaluate_files(args.dataset, args.candidate)
    run_output = args.output_dir / report.dataset_id / report.candidate_id
    json_path, markdown_path = write_report(report, run_output)
    failures = check_thresholds(
        report,
        BidBenchThresholds(
            min_mandatory_recall=args.min_mandatory_recall,
            min_scored_recall=args.min_scored_recall,
            min_source_association_accuracy=args.min_source_association_accuracy,
            min_combined_score=args.min_combined_score,
            max_unsupported_claim_rate=args.max_unsupported_claim_rate,
        ),
    )

    print(f"BidBench combined score: {report.metrics.combined_score:.2%}")
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {markdown_path}")
    if failures:
        print("Quality gate failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
