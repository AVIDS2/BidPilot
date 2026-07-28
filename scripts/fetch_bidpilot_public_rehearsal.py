"""Fetch the pinned public BidPilot rehearsal pack into ignored local storage.

The repository stores only public source metadata and pinned hashes. Raw source
files are deliberately fetched into ``tmp/`` so third-party material, public
contact data, and upstream changes are never silently committed to Git.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path, PurePath
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST = REPOSITORY_ROOT / "sample-data" / "bidpilot-public-rehearsal" / "manifest.json"
DEFAULT_OUTPUT_DIR = Path("tmp") / "p0-d7-public-rehearsal"
MAX_DOCUMENT_BYTES = 8 * 1024 * 1024
READ_SIZE = 64 * 1024
USER_AGENT = "BidPilot-P0-D7-Rehearsal/1.0 (+https://github.com/AVIDS2/BidPilot)"


class PublicRehearsalError(RuntimeError):
    """Raised when the public rehearsal source contract is not satisfied."""


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch the pinned public BidPilot rehearsal pack.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--timeout-seconds", type=float, default=60.0)
    parser.add_argument("--refresh", action="store_true", help="redownload verified files into the ignored output directory")
    parser.add_argument("--verify-only", action="store_true", help="validate existing files without making network requests")
    return parser.parse_args()


def _repository_path(path: Path) -> Path:
    return path if path.is_absolute() else REPOSITORY_ROOT / path


def _safe_output_dir(path: Path) -> Path:
    candidate = _repository_path(path).resolve()
    tmp_root = (REPOSITORY_ROOT / "tmp").resolve()
    try:
        candidate.relative_to(tmp_root)
    except ValueError as exc:
        raise PublicRehearsalError("Public rehearsal output must stay below the ignored repository tmp/ directory") from exc
    return candidate


def _safe_filename(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise PublicRehearsalError("Manifest document filename is required")
    path = PurePath(value)
    if path.name != value or path.suffix.lower() != ".pdf":
        raise PublicRehearsalError("Manifest documents must use a simple .pdf filename")
    return value


def _required_string(document: dict[str, Any], key: str) -> str:
    value = document.get(key)
    if not isinstance(value, str) or not value.strip():
        raise PublicRehearsalError(f"Manifest document {key} is required")
    return value.strip()


def _load_manifest(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]], str]:
    resolved = _repository_path(path)
    try:
        raw = resolved.read_bytes()
        manifest = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise PublicRehearsalError(f"Could not read public rehearsal manifest: {resolved}") from exc

    if not isinstance(manifest, dict):
        raise PublicRehearsalError("Public rehearsal manifest must be a JSON object")
    if manifest.get("origin") != "public_historical_procurement":
        raise PublicRehearsalError("Public rehearsal manifest has an unexpected origin")
    _required_string(manifest, "dataset_id")
    if not isinstance(manifest.get("dataset_version"), int) or manifest["dataset_version"] < 1:
        raise PublicRehearsalError("Public rehearsal manifest dataset_version must be a positive integer")

    documents = manifest.get("documents")
    if not isinstance(documents, list) or len(documents) < 3:
        raise PublicRehearsalError("Public rehearsal manifest must contain at least three documents")

    seen_ids: set[str] = set()
    seen_filenames: set[str] = set()
    for document in documents:
        if not isinstance(document, dict):
            raise PublicRehearsalError("Public rehearsal document entries must be objects")
        document_id = _required_string(document, "id")
        if document_id in seen_ids:
            raise PublicRehearsalError("Public rehearsal document ids must be unique")
        seen_ids.add(document_id)

        filename = _safe_filename(document.get("filename"))
        if filename in seen_filenames:
            raise PublicRehearsalError("Public rehearsal filenames must be unique")
        seen_filenames.add(filename)

        source_url = _required_string(document, "source_url")
        parsed_url = urlparse(source_url)
        if parsed_url.scheme != "https" or not parsed_url.hostname:
            raise PublicRehearsalError("Public rehearsal source URLs must use HTTPS")
        if _required_string(document, "content_type") != "application/pdf":
            raise PublicRehearsalError("Public rehearsal documents must be application/pdf")

        digest = _required_string(document, "sha256").lower()
        if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
            raise PublicRehearsalError("Public rehearsal document sha256 must be lowercase hexadecimal")
        if not isinstance(document.get("expected_bytes"), int) or document["expected_bytes"] <= 0:
            raise PublicRehearsalError("Public rehearsal document expected_bytes must be positive")
        for key in ("role", "title", "source_publisher", "source_published_at"):
            _required_string(document, key)

    return manifest, documents, hashlib.sha256(raw).hexdigest()


def _verify_file(path: Path, document: dict[str, Any]) -> dict[str, object]:
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise PublicRehearsalError(f"Missing rehearsal source file: {path.name}") from exc

    digest = hashlib.sha256(data).hexdigest()
    if len(data) != document["expected_bytes"]:
        raise PublicRehearsalError(f"Pinned byte length differs for {path.name}; review the upstream source before refreshing")
    if digest != document["sha256"]:
        raise PublicRehearsalError(f"Pinned SHA-256 differs for {path.name}; review the upstream source before refreshing")
    if not data.startswith(b"%PDF-"):
        raise PublicRehearsalError(f"Downloaded source is not a PDF: {path.name}")
    return {"id": document["id"], "filename": path.name, "bytes": len(data), "sha256": digest}


def _download_file(path: Path, document: dict[str, Any], timeout_seconds: float) -> dict[str, object]:
    source_url = str(document["source_url"])
    temporary_path = path.with_suffix(f"{path.suffix}.part")
    temporary_path.unlink(missing_ok=True)
    digest = hashlib.sha256()
    total_bytes = 0
    signature = b""
    completed = False

    try:
        request = Request(source_url, headers={"User-Agent": USER_AGENT, "Accept": "application/pdf"})
        with urlopen(request, timeout=timeout_seconds) as response, temporary_path.open("wb") as output:
            resolved_url = urlparse(response.geturl())
            if resolved_url.scheme != "https" or not resolved_url.hostname:
                raise PublicRehearsalError("Public rehearsal source redirected outside HTTPS")
            content_type = response.headers.get_content_type().lower()
            if content_type != "application/pdf":
                raise PublicRehearsalError(f"Source did not return application/pdf for {path.name}")
            while chunk := response.read(READ_SIZE):
                total_bytes += len(chunk)
                if total_bytes > MAX_DOCUMENT_BYTES:
                    raise PublicRehearsalError(f"Public rehearsal source exceeds {MAX_DOCUMENT_BYTES} bytes: {path.name}")
                if len(signature) < 5:
                    signature += chunk[: 5 - len(signature)]
                digest.update(chunk)
                output.write(chunk)
        completed = True
    except HTTPError as exc:
        raise PublicRehearsalError(f"Public rehearsal download returned HTTP {exc.code} for {path.name}") from exc
    except URLError as exc:
        raise PublicRehearsalError(f"Public rehearsal download failed for {path.name}") from exc
    finally:
        if not completed:
            temporary_path.unlink(missing_ok=True)

    if signature != b"%PDF-":
        temporary_path.unlink(missing_ok=True)
        raise PublicRehearsalError(f"Downloaded source is not a PDF: {path.name}")
    if total_bytes != document["expected_bytes"] or digest.hexdigest() != document["sha256"]:
        temporary_path.unlink(missing_ok=True)
        raise PublicRehearsalError(f"Pinned source changed for {path.name}; update the manifest only after review")

    # The source is validated before it becomes the current local rehearsal input.
    temporary_path.replace(path)
    return {"id": document["id"], "filename": path.name, "bytes": total_bytes, "sha256": digest.hexdigest()}


def _write_receipt(output_dir: Path, manifest: dict[str, Any], manifest_hash: str, documents: list[dict[str, object]]) -> None:
    receipt = {
        "schema_version": "1.0",
        "dataset_id": manifest["dataset_id"],
        "dataset_version": manifest["dataset_version"],
        "manifest_sha256": manifest_hash,
        "retrieved_at": datetime.now(UTC).isoformat(),
        "documents": documents,
    }
    (output_dir / "fetched-manifest.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def main() -> int:
    args = _parse_args()
    if args.timeout_seconds <= 0:
        print("--timeout-seconds must be positive", file=sys.stderr)
        return 2
    if args.verify_only and args.refresh:
        print("--verify-only and --refresh cannot be used together", file=sys.stderr)
        return 2

    try:
        manifest, documents, manifest_hash = _load_manifest(args.manifest)
        output_dir = _safe_output_dir(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        receipt_documents: list[dict[str, object]] = []
        for document in documents:
            target = output_dir / str(document["filename"])
            if target.exists() and not args.refresh:
                receipt_documents.append(_verify_file(target, document))
                print(f"verified {document['id']}", flush=True)
                continue
            if args.verify_only:
                raise PublicRehearsalError(f"Missing rehearsal source file: {target.name}")
            receipt_documents.append(_download_file(target, document, args.timeout_seconds))
            print(f"fetched {document['id']}", flush=True)
        _write_receipt(output_dir, manifest, manifest_hash, receipt_documents)
        print(f"public_rehearsal_dir={output_dir}", flush=True)
        return 0
    except PublicRehearsalError as exc:
        print(f"Public rehearsal fetch failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
