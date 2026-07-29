"""Shared contracts for immutable source-document ingestion.

The API owns upload validation and the Worker owns parsing/indexing, but both
must agree on the same durable status values.  These constants deliberately
describe persisted business state rather than a UI-only progress indicator.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import PurePath


class DocumentParseStatus(StrEnum):
    PENDING = "pending"
    PARSING = "parsing"
    PARSED = "parsed"
    FAILED = "failed"


class DocumentIndexStatus(StrEnum):
    PENDING = "pending"
    INDEXING = "indexing"
    INDEXED = "indexed"
    DEGRADED = "degraded"
    FAILED = "failed"


class BundleIngestStatus(StrEnum):
    AWAITING_UPLOAD = "awaiting_upload"
    READY_TO_INGEST = "ready_to_ingest"
    QUEUED = "queued"
    RUNNING = "running"
    INDEXING = "indexing"
    INGESTED = "ingested"
    PARTIAL_FAILURE = "partial_failure"
    FAILED = "failed"


MAX_SOURCE_DOCUMENT_BYTES = 25 * 1024 * 1024
MAX_DOCUMENT_PARSE_ATTEMPTS = 3

_GENERIC_CONTENT_TYPES = {"", "application/octet-stream", "binary/octet-stream"}
_MIME_BY_EXTENSION = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
}
SUPPORTED_SOURCE_DOCUMENT_MIME_TYPES = frozenset(_MIME_BY_EXTENSION.values())

# A bundle is not just a storage bucket.  Requirement Ledger entries are buyer
# obligations, so supplier capability and case-study material must remain
# retrievable evidence instead of being misclassified as procurement demands.
REQUIREMENT_SOURCE_BUNDLE_TYPES = frozenset(
    {
        "assistant_upload",
        "buyer_rfp",
        "public_rehearsal",
        "rfp",
        "synthetic_fixture",
        "tender",
        "upload",
    }
)


def bundle_contributes_requirements(source_type: str) -> bool:
    """Return whether a bundle may materialize buyer requirements.

    ``upload`` and ``assistant_upload`` remain eligible for backwards
    compatibility with the existing generic upload flow.  New governed flows
    should use ``buyer_rfp`` for buyer material and ``supplier_evidence`` for
    capability, case-study, or internal supporting material.
    """

    return source_type.strip().lower() in REQUIREMENT_SOURCE_BUNDLE_TYPES


def canonical_source_document_mime_type(*, filename: str, content_type: str) -> str | None:
    """Return a supported canonical MIME type without trusting a browser hint.

    A known browser MIME type wins.  Only generic upload types may fall back to
    a filename extension, so an explicitly unsupported type cannot masquerade
    as a supported document merely by being renamed.
    """

    normalized = content_type.split(";", 1)[0].strip().lower()
    if normalized in SUPPORTED_SOURCE_DOCUMENT_MIME_TYPES:
        return normalized
    if normalized not in _GENERIC_CONTENT_TYPES:
        return None
    return _MIME_BY_EXTENSION.get(PurePath(filename).suffix.lower())


def source_document_validation_error(*, data: bytes, mime_type: str) -> str | None:
    """Return a safe public validation code, never parser/provider details."""

    if not data:
        return "empty_document"
    if len(data) > MAX_SOURCE_DOCUMENT_BYTES:
        return "document_too_large"
    if mime_type == "application/pdf" and not data.startswith(b"%PDF-"):
        return "invalid_pdf_signature"
    if mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document" and not data.startswith(b"PK"):
        return "invalid_docx_signature"
    return None


__all__ = [
    "BundleIngestStatus",
    "DocumentIndexStatus",
    "DocumentParseStatus",
    "MAX_DOCUMENT_PARSE_ATTEMPTS",
    "MAX_SOURCE_DOCUMENT_BYTES",
    "REQUIREMENT_SOURCE_BUNDLE_TYPES",
    "SUPPORTED_SOURCE_DOCUMENT_MIME_TYPES",
    "bundle_contributes_requirements",
    "canonical_source_document_mime_type",
    "source_document_validation_error",
]
