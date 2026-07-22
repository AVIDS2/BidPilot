"""Score a captured BidPilot Assistant router run without invoking a provider."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
API_ROOT = REPO_ROOT / "services" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.evaluation.assistant_metrics import (  # noqa: E402
    load_assistant_benchmark_dataset,
    load_assistant_evaluation_run,
    score_assistant_run,
    write_assistant_report,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Score a captured BidPilot Assistant router/policy run without calling a provider."
    )
    parser.add_argument("--dataset", type=Path, required=True, help="frozen AssistantBench fixture JSON")
    parser.add_argument("--run", type=Path, required=True, help="redacted AssistantBench evaluation run JSON")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "output" / "bidbench-assistant",
        help="directory for the generated report",
    )
    parser.add_argument(
        "--require-controlled-capture",
        action="store_true",
        help="fail unless the run has reviewed model/provenance and perfect policy-safety evidence",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    dataset = load_assistant_benchmark_dataset(args.dataset)
    run = load_assistant_evaluation_run(args.run)
    report = score_assistant_run(dataset, run)
    output_root = args.output_dir.resolve()
    output_dir = (output_root / report.dataset_id / report.fixture_fingerprint[:12]).resolve()
    if not output_dir.is_relative_to(output_root):
        print("Resolved output path escapes --output-dir", file=sys.stderr)
        return 2

    json_path, markdown_path = write_assistant_report(report, output_dir)
    print(f"Intent mode accuracy: {report.metrics.mode_accuracy:.2%}")
    print(f"Capability route accuracy: {_format_rate(report.metrics.capability_route_accuracy)}")
    print(f"Policy outcome accuracy: {_format_rate(report.metrics.policy_outcome_accuracy)}")
    print(f"Typed-confirmation safety: {_format_rate(report.metrics.typed_confirmation_safety_rate)}")
    print(f"Project-scope safety: {_format_rate(report.metrics.project_scope_safety_rate)}")
    print(f"Unknown capability rate: {report.metrics.unknown_capability_rate:.2%}")
    print(f"Controlled capture ready: {report.capture_readiness.controlled_capture_ready}")
    for failure in report.capture_readiness.failures:
        print(f"Capture evidence gap: {failure}", file=sys.stderr)
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {markdown_path}")
    return 1 if args.require_controlled_capture and not report.capture_readiness.controlled_capture_ready else 0


def _format_rate(value: float | None) -> str:
    return "not applicable" if value is None else f"{value:.2%}"


if __name__ == "__main__":
    raise SystemExit(main())
