"""Score a captured governed-memory context run without calling providers."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
API_ROOT = REPO_ROOT / "services" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.evaluation.memory_metrics import (  # noqa: E402
    load_memory_benchmark_dataset,
    load_memory_evaluation_run,
    score_memory_run,
    write_memory_report,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Score a captured BidPilot memory context run without calling a provider."
    )
    parser.add_argument("--dataset", type=Path, required=True, help="frozen MemoryBench fixture JSON")
    parser.add_argument("--run", type=Path, required=True, help="redacted memory evaluation run JSON")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "output" / "bidbench-memory",
        help="directory for the generated report",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    dataset = load_memory_benchmark_dataset(args.dataset)
    run = load_memory_evaluation_run(args.run)
    report = score_memory_run(dataset, run)
    output_root = args.output_dir.resolve()
    output_dir = (output_root / report.dataset_id / report.fixture_fingerprint[:12]).resolve()
    if not output_dir.is_relative_to(output_root):
        print("Resolved output path escapes --output-dir", file=sys.stderr)
        return 2

    json_path, markdown_path = write_memory_report(report, output_dir)
    print(f"Expected record recall: {report.metrics.expected_record_recall:.2%}")
    print(f"Isolation pass: {report.metrics.isolation_pass_rate:.2%}")
    print(f"Provenance validity: {report.metrics.provenance_validity_rate:.2%}")
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
