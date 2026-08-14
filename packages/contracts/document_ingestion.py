"""Shared contracts for immutable source-document ingestion.

The API owns upload validation and the Worker owns parsing/indexing, but both
must agree on the same durable status values.  These constants deliberately
describe persisted business state rather than a UI-only progress indicator.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import PurePath


class DocumentParseStatus(StrEnum):
    NOT_APPLICABLE = "not_applicable"
    PENDING = "pending"
    PARSING = "parsing"
    PARSED = "parsed"
    FAILED = "failed"


class DocumentIndexStatus(StrEnum):
    NOT_APPLICABLE = "not_applicable"
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
# Downloadable supporting artifacts (for example bidder software packages)
# are not parsed or embedded. Keep a separate bounded limit so a legitimate
# ZIP does not get rejected by the text-document ingestion limit while still
# preventing an unbounded agent-triggered download.
MAX_STORED_ARTIFACT_BYTES = 512 * 1024 * 1024
MAX_DOCUMENT_PARSE_ATTEMPTS = 3

_GENERIC_CONTENT_TYPES = {"", "application/octet-stream", "binary/octet-stream"}
_MIME_BY_EXTENSION = {
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".ppt": "application/vnd.ms-powerpoint",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".zip": "application/zip",
    ".rar": "application/vnd.rar",
    ".7z": "application/x-7z-compressed",
    ".csv": "text/csv",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
}
PARSEABLE_SOURCE_DOCUMENT_MIME_TYPES = frozenset(
    {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "text/csv",
        "text/plain",
        "text/markdown",
    }
)
STORED_ARTIFACT_MIME_TYPES = frozenset(
    {
        "application/msword",
        "application/vnd.ms-excel",
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/zip",
        "application/vnd.rar",
        "application/x-7z-compressed",
    }
)
SUPPORTED_SOURCE_DOCUMENT_MIME_TYPES = PARSEABLE_SOURCE_DOCUMENT_MIME_TYPES | STORED_ARTIFACT_MIME_TYPES

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


def source_document_is_parseable(mime_type: str) -> bool:
    """Return whether the ingestion worker can extract searchable text."""

    return mime_type in PARSEABLE_SOURCE_DOCUMENT_MIME_TYPES


def source_document_validation_error(*, data: bytes, mime_type: str) -> str | None:
    """Return a safe public validation code, never parser/provider details."""

    if not data:
        return "empty_document"
    byte_limit = (
        MAX_STORED_ARTIFACT_BYTES
        if mime_type in STORED_ARTIFACT_MIME_TYPES
        else MAX_SOURCE_DOCUMENT_BYTES
    )
    if len(data) > byte_limit:
        return "document_too_large"
    if mime_type == "application/pdf" and not data.startswith(b"%PDF-"):
        return "invalid_pdf_signature"
    if mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document" and not data.startswith(b"PK"):
        return "invalid_docx_signature"
    if mime_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" and not data.startswith(b"PK"):
        return "invalid_xlsx_signature"
    if mime_type == "application/zip" and not data.startswith(b"PK"):
        return "invalid_zip_signature"
    if mime_type == "application/vnd.rar" and not data.startswith(b"Rar!"):
        return "invalid_rar_signature"
    if mime_type == "application/x-7z-compressed" and not data.startswith(b"7z\xbc\xaf\x27\x1c"):
        return "invalid_7z_signature"
    return None


__all__ = [
    "BundleIngestStatus",
    "DocumentIndexStatus",
    "DocumentParseStatus",
    "MAX_DOCUMENT_PARSE_ATTEMPTS",
    "MAX_STORED_ARTIFACT_BYTES",
    "MAX_SOURCE_DOCUMENT_BYTES",
    "PARSEABLE_SOURCE_DOCUMENT_MIME_TYPES",
    "REQUIREMENT_SOURCE_BUNDLE_TYPES",
    "STORED_ARTIFACT_MIME_TYPES",
    "SUPPORTED_SOURCE_DOCUMENT_MIME_TYPES",
    "bundle_contributes_requirements",
    "canonical_source_document_mime_type",
    "source_document_validation_error",
    "source_document_is_parseable",
]
