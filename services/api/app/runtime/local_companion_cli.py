"""Console entry point for the user-owned BidPilot local companion.

The command is deliberately local and narrow: it downloads one already
confirmed public artifact to a directory chosen by the local user.  It never
accepts shell snippets, runs in the server container, or sends a local path
back to BidPilot.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from .local_companion import LocalArtifactRequest, download_local_artifact


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="BidPilot local artifact companion")
    subparsers = parser.add_subparsers(dest="command", required=True)
    download = subparsers.add_parser(
        "download",
        help="stream one confirmed HTTP(S) artifact into a local directory",
    )
    download.add_argument("--request-id", required=True)
    download.add_argument("--url", required=True)
    download.add_argument("--filename", required=True)
    download.add_argument("--directory", type=Path, required=True)
    download.add_argument("--allow-host", action="append", default=[])
    download.add_argument("--max-bytes", type=int, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command != "download":  # argparse keeps this defensive branch explicit.
        raise ValueError(f"Unsupported local companion command: {args.command}")

    request_data = {
        "request_id": args.request_id,
        "url": args.url,
        "filename": args.filename,
    }
    if args.max_bytes is not None:
        request_data["max_bytes"] = args.max_bytes
    receipt = download_local_artifact(
        LocalArtifactRequest.model_validate(request_data),
        destination_directory=args.directory,
        allowed_hosts=args.allow_host,
    )
    print(receipt.model_dump_json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
