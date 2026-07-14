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
    apply_thresholds,
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
    parser.add_argument(
        "--informational",
        action="store_true",
        help="write a report without enforcing thresholds",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = evaluate_files(args.dataset, args.candidate)
    thresholds = BidBenchThresholds(
        min_mandatory_recall=args.min_mandatory_recall,
        min_scored_recall=args.min_scored_recall,
        min_source_association_accuracy=args.min_source_association_accuracy,
        min_combined_score=args.min_combined_score,
        max_unsupported_claim_rate=args.max_unsupported_claim_rate,
    )
    has_threshold = any(value is not None for value in thresholds.model_dump().values())
    if not args.informational and not has_threshold:
        print(
            "Refusing a false-green run: provide at least one threshold or use --informational.",
            file=sys.stderr,
        )
        return 2
    report = apply_thresholds(report, thresholds, informational=args.informational)
    output_root = args.output_dir.resolve()
    run_output = (
        output_root
        / report.dataset_id
        / report.candidate_id
        / report.input_fingerprint[:12]
    ).resolve()
    if not run_output.is_relative_to(output_root):
        print("Resolved output path escapes --output-dir", file=sys.stderr)
        return 2
    json_path, markdown_path = write_report(report, run_output)
    failures = report.gate.failures if report.gate is not None else []

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
