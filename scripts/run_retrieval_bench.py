"""Score a captured Retrieval 2.0 run against a frozen BidBench fixture."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
API_ROOT = REPO_ROOT / "services" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.evaluation.retrieval_metrics import (  # noqa: E402
    load_retrieval_benchmark_dataset,
    load_retrieval_evaluation_run,
    score_retrieval_run,
    write_retrieval_report,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Score a captured project-scoped retrieval run without calling a provider."
    )
    parser.add_argument("--dataset", type=Path, required=True, help="frozen retrieval benchmark JSON")
    parser.add_argument("--run", type=Path, required=True, help="captured retrieval run JSON")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "output" / "bidbench-retrieval",
        help="directory for the generated report",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    dataset = load_retrieval_benchmark_dataset(args.dataset)
    run = load_retrieval_evaluation_run(args.run)
    report = score_retrieval_run(dataset, run)
    output_root = args.output_dir.resolve()
    output_dir = (
        output_root
        / report.dataset_id
        / report.strategy.value
        / report.fixture_fingerprint[:12]
    ).resolve()
    if not output_dir.is_relative_to(output_root):
        print("Resolved output path escapes --output-dir", file=sys.stderr)
        return 2

    json_path, markdown_path = write_retrieval_report(report, output_dir)
    print(f"Recall@10: {report.metrics.recall_at_10:.2%}")
    print(f"MRR: {report.metrics.mean_reciprocal_rank:.2%}")
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
