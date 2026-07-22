"""Create a redacted BidBench candidate from a reviewed Claim Integrity run."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
API_ROOT = REPO_ROOT / "services" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.db import SessionLocal  # noqa: E402
from app.evaluation.claim_integrity_runtime_capture import (  # noqa: E402
    capture_claim_integrity_runtime_candidate,
    load_claim_integrity_runtime_capture_manifest,
)
from contracts import BidBenchDataset  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture one redacted BidBench candidate from a reviewed Claim Integrity workflow run."
    )
    parser.add_argument("--dataset", type=Path, required=True, help="frozen BidBench dataset JSON")
    parser.add_argument("--manifest", type=Path, required=True, help="private reviewed runtime mapping")
    parser.add_argument(
        "--output-file",
        type=Path,
        default=REPO_ROOT / "output" / "claim-integrity-runtime-capture" / "candidate.json",
    )
    parser.add_argument(
        "--confirm-redacted-claim-capture",
        action="store_true",
        help="required acknowledgement that only approved synthetic/public traces are mapped",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.confirm_redacted_claim_capture:
        print("--confirm-redacted-claim-capture is required", file=sys.stderr)
        return 2
    output_file = args.output_file.resolve()
    output_root = (REPO_ROOT / "output").resolve()
    if not output_file.is_relative_to(output_root):
        print("--output-file must remain under the repository output directory", file=sys.stderr)
        return 2

    try:
        dataset = BidBenchDataset.model_validate_json(args.dataset.read_bytes())
        manifest = load_claim_integrity_runtime_capture_manifest(args.manifest)
        with SessionLocal() as db:
            candidate = capture_claim_integrity_runtime_candidate(db, dataset, manifest)
    except ValueError as exc:
        print(f"Claim Integrity capture error: {exc}", file=sys.stderr)
        return 2

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(candidate.model_dump_json(indent=2), encoding="utf-8")
    print(f"Captured redacted Claim Integrity candidate: {output_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
