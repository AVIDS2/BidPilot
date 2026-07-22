from __future__ import annotations

import argparse
import sys
import tempfile
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
from app.evaluation.adapters import (  # noqa: E402
    build_candidate_from_requirement_snapshot,
    load_current_pipeline_trace_map,
)
from contracts import BidBenchDataset  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Score a saved BidBench candidate without calling a model provider."
    )
    parser.add_argument("--dataset", type=Path, required=True, help="dataset directory or dataset.json")
    candidate_input = parser.add_mutually_exclusive_group(required=True)
    candidate_input.add_argument("--candidate", type=Path, help="saved candidate JSON")
    candidate_input.add_argument(
        "--requirements-snapshot",
        type=Path,
        help="saved current Requirement Ledger list/detail response",
    )
    parser.add_argument(
        "--trace-map",
        type=Path,
        help="reviewed platform-id to BidBench-id mapping for snapshot mode",
    )
    parser.add_argument(
        "--candidate-id",
        help="stable candidate id required for --requirements-snapshot",
    )
    parser.add_argument("--git-commit", help="optional source revision for snapshot mode")
    parser.add_argument("--provider", help="optional provider metadata for snapshot mode")
    parser.add_argument("--model", help="optional model metadata for snapshot mode")
    parser.add_argument("--prompt-version", default="current-requirement-api-v2")
    parser.add_argument("--run-number", type=int, default=1)
    parser.add_argument("--latency-ms", type=int)
    parser.add_argument("--estimated-cost-usd", type=float)
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
    parser.add_argument("--min-claim-trace-integrity-rate", type=float)
    parser.add_argument(
        "--informational",
        action="store_true",
        help="write a report without enforcing thresholds",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.requirements_snapshot and not args.candidate_id:
        print("--candidate-id is required with --requirements-snapshot", file=sys.stderr)
        return 2
    if args.candidate and (args.trace_map or args.candidate_id):
        print("--trace-map and --candidate-id are only valid with --requirements-snapshot", file=sys.stderr)
        return 2

    candidate_bytes: bytes
    with tempfile.TemporaryDirectory(prefix="bidbench-") as temp_dir:
        candidate_path = _resolve_candidate_input(args, Path(temp_dir))
        candidate_bytes = candidate_path.read_bytes()
        report = evaluate_files(args.dataset, candidate_path)
    thresholds = BidBenchThresholds(
        min_mandatory_recall=args.min_mandatory_recall,
        min_scored_recall=args.min_scored_recall,
        min_source_association_accuracy=args.min_source_association_accuracy,
        min_combined_score=args.min_combined_score,
        max_unsupported_claim_rate=args.max_unsupported_claim_rate,
        min_claim_trace_integrity_rate=args.min_claim_trace_integrity_rate,
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
    normalized_candidate_path = run_output / "candidate.json"
    normalized_candidate_path.write_bytes(candidate_bytes)
    failures = report.gate.failures if report.gate is not None else []

    print(f"BidBench combined score: {report.metrics.combined_score:.2%}")
    print(f"Candidate: {normalized_candidate_path}")
    print(f"JSON report: {json_path}")
    print(f"Markdown report: {markdown_path}")
    if failures:
        print("Quality gate failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    return 0


def _resolve_candidate_input(args: argparse.Namespace, temporary_dir: Path) -> Path:
    if args.candidate:
        return args.candidate

    dataset_file = _resolve_dataset_file(args.dataset)
    try:
        dataset = BidBenchDataset.model_validate_json(dataset_file.read_bytes())
    except (OSError, ValueError) as exc:
        raise ValueError(f"invalid BidBench dataset: {dataset_file}") from exc

    trace_map = load_current_pipeline_trace_map(args.trace_map) if args.trace_map else None
    candidate = build_candidate_from_requirement_snapshot(
        snapshot_path=args.requirements_snapshot,
        dataset_id=dataset.dataset_id,
        candidate_id=args.candidate_id,
        git_commit=args.git_commit,
        trace_map=trace_map,
        provider=args.provider,
        model=args.model,
        prompt_version=args.prompt_version,
        run_number=args.run_number,
        latency_ms=args.latency_ms,
        estimated_cost_usd=args.estimated_cost_usd,
    )
    candidate_path = temporary_dir / "normalized-candidate.json"
    candidate_path.write_text(candidate.model_dump_json(indent=2), encoding="utf-8")
    return candidate_path


def _resolve_dataset_file(dataset_path: Path) -> Path:
    if dataset_path.is_dir():
        return dataset_path / "dataset.json"
    return dataset_path


if __name__ == "__main__":
    raise SystemExit(main())
