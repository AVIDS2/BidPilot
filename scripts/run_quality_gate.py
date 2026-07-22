"""Apply the reviewed BidPilot quality policy to captured evaluation reports."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
API_ROOT = REPO_ROOT / "services" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.evaluation.release_gate import (  # noqa: E402
    QualityGateMode,
    evaluate_quality_gate,
    load_assistant_report,
    load_bidbench_report,
    load_memory_report,
    load_quality_gate_policy,
    load_retrieval_report,
    write_quality_gate_report,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Apply a BidPilot quality policy to captured offline evaluation reports."
    )
    parser.add_argument("--policy", type=Path, required=True, help="reviewed quality-gate policy JSON")
    parser.add_argument("--bidbench-report", type=Path, required=True)
    parser.add_argument("--retrieval-report", type=Path, required=True)
    parser.add_argument("--memory-report", type=Path, required=True)
    parser.add_argument("--assistant-report", type=Path, required=True)
    parser.add_argument("--mode", type=QualityGateMode, choices=list(QualityGateMode), required=True)
    parser.add_argument(
        "--expected-git-commit",
        help="required in release mode; every report must declare this exact revision",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "output" / "quality-gate",
        help="directory for the immutable gate report",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.mode is QualityGateMode.RELEASE and not args.expected_git_commit:
        print("--expected-git-commit is required in release mode", file=sys.stderr)
        return 2

    try:
        policy = load_quality_gate_policy(args.policy)
        report = evaluate_quality_gate(
            policy,
            bidbench_report=load_bidbench_report(args.bidbench_report),
            retrieval_report=load_retrieval_report(args.retrieval_report),
            memory_report=load_memory_report(args.memory_report),
            assistant_report=load_assistant_report(args.assistant_report),
            mode=args.mode,
            expected_git_commit=args.expected_git_commit,
        )
    except ValueError as exc:
        print(f"quality-gate input error: {exc}", file=sys.stderr)
        return 2

    output_root = args.output_dir.resolve()
    output_dir = (
        output_root / policy.policy_id / report.input_fingerprint[:12]
    ).resolve()
    if not output_dir.is_relative_to(output_root):
        print("resolved output path escapes --output-dir", file=sys.stderr)
        return 2
    json_path, markdown_path = write_quality_gate_report(report, output_dir)
    print(f"Quality gate passed: {report.passed}")
    print(f"Release eligible: {report.release_eligible}")
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {markdown_path}")
    if report.failures:
        print("Quality gate failures:", file=sys.stderr)
        for failure in report.failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
