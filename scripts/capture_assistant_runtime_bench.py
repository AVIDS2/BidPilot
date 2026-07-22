"""Create a redacted AssistantBench candidate from approved runtime traces."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
API_ROOT = REPO_ROOT / "services" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.db import SessionLocal  # noqa: E402
from app.evaluation.assistant_metrics import load_assistant_benchmark_dataset  # noqa: E402
from app.evaluation.assistant_runtime_capture import (  # noqa: E402
    capture_assistant_runtime_run,
    load_assistant_runtime_capture_manifest,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture one redacted AssistantBench candidate from approved Operator runtime runs."
    )
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument(
        "--output-file",
        type=Path,
        default=REPO_ROOT / "output" / "assistant-runtime-capture" / "candidate-run.json",
    )
    parser.add_argument(
        "--confirm-redacted-runtime-capture",
        action="store_true",
        help="required acknowledgement that only approved synthetic/public test runs are mapped",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.confirm_redacted_runtime_capture:
        print("--confirm-redacted-runtime-capture is required", file=sys.stderr)
        return 2
    output_file = args.output_file.resolve()
    output_root = (REPO_ROOT / "output").resolve()
    if not output_file.is_relative_to(output_root):
        print("--output-file must remain under the repository output directory", file=sys.stderr)
        return 2

    try:
        dataset = load_assistant_benchmark_dataset(args.dataset)
        manifest = load_assistant_runtime_capture_manifest(args.manifest)
        with SessionLocal() as db:
            run = capture_assistant_runtime_run(db, dataset, manifest)
    except ValueError as exc:
        print(f"AssistantBench capture error: {exc}", file=sys.stderr)
        return 2

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(run.model_dump_json(indent=2), encoding="utf-8")
    print(f"Captured redacted AssistantBench run: {output_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
