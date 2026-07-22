"""Score a captured Bid Wiki graph-proposal run without calling providers."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
API_ROOT = REPO_ROOT / "services" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.evaluation.memory_graph_metrics import (  # noqa: E402
    load_memory_graph_benchmark_dataset,
    load_memory_graph_evaluation_run,
    score_memory_graph_run,
    write_memory_graph_report,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Score a captured BidPilot memory graph proposal run without calling a provider."
    )
    parser.add_argument("--dataset", type=Path, required=True, help="frozen MemoryGraphBench fixture JSON")
    parser.add_argument("--run", type=Path, required=True, help="redacted graph proposal evaluation run JSON")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "output" / "bidbench-memory-graph",
        help="directory for the generated report",
    )
    parser.add_argument(
        "--require-controlled-capture",
        action="store_true",
        help="fail unless the run has model/provenance/review evidence suitable for baseline analysis",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    dataset = load_memory_graph_benchmark_dataset(args.dataset)
    run = load_memory_graph_evaluation_run(args.run)
    report = score_memory_graph_run(dataset, run)
    output_root = args.output_dir.resolve()
    output_dir = (output_root / report.dataset_id / report.fixture_fingerprint[:12]).resolve()
    if not output_dir.is_relative_to(output_root):
        print("Resolved output path escapes --output-dir", file=sys.stderr)
        return 2

    json_path, markdown_path = write_memory_graph_report(report, output_dir)
    print(f"Schema validity: {report.metrics.schema_validity_rate:.2%}")
    print(f"Scope isolation: {report.metrics.scope_isolation_pass_rate:.2%}")
    print(f"Entity precision / recall: {report.metrics.entity_precision:.2%} / {report.metrics.entity_recall:.2%}")
    print(f"Relation precision / recall: {report.metrics.relation_precision:.2%} / {report.metrics.relation_recall:.2%}")
    print(f"Evidence validity: {report.metrics.evidence_validity_rate:.2%}")
    print(f"Grounded relation recall: {report.metrics.grounded_relation_recall:.2%}")
    print(f"Provider/model: {report.provider or 'not recorded'} / {report.model or 'not recorded'}")
    if report.metrics.review_summary_validity_rate is not None:
        print(f"Review summary validity: {report.metrics.review_summary_validity_rate:.2%}")
        print(f"Review decision coverage: {report.metrics.review_decision_coverage_rate:.2%}")
        print(f"Full review completion: {report.metrics.full_review_completion_rate:.2%}")
    else:
        print("Review summary: not captured")
    print(f"Controlled capture ready: {report.capture_readiness.controlled_capture_ready}")
    for failure in report.capture_readiness.failures:
        print(f"Capture evidence gap: {failure}", file=sys.stderr)
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {markdown_path}")
    return 1 if args.require_controlled_capture and not report.capture_readiness.controlled_capture_ready else 0


if __name__ == "__main__":
    raise SystemExit(main())
