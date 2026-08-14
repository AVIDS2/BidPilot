"""Parser adapter for document ingestion.

Extracts text from PDF (PyMuPDF) and DOCX (python-docx), then splits into
hierarchical chunks with heading-aware boundaries, table detection, and
structured metadata for retrieval quality.
"""

import hashlib
import io
import logging
import re
import csv
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.db import SessionLocal
from app.models import Bundle, KnowledgeChunk, ParsedAsset, SourceDocument
from app.retrieval.normalization import normalize_retrieval_text
from contracts.document_ingestion import (
    DocumentIndexStatus,
    DocumentParseStatus,
    MAX_DOCUMENT_PARSE_ATTEMPTS,
)
from sqlalchemy import select

logger = logging.getLogger(__name__)

CHUNK_SIZE_CHARS = 1500   # Slightly larger to keep sections together
MAX_SECTION_CHARS = 3000  # Hard cap for a single section before sub-splitting
PARSER_NAME = "docpilot-hierarchical"
PARSER_VERSION = "3.1"
_OCR_TEXT_THRESHOLD = 24


@dataclass
class ParsedChunk:
    chunk_index: int
    content: str
    chunk_key: str
    metadata: dict = field(default_factory=dict)


@dataclass
class ParsedDocument:
    """One immutable source-document version after a pure parse attempt."""

    source_document_id: str
    source_checksum: str
    version_number: int
    normalized_text: str = ""
    chunks: list[ParsedChunk] = field(default_factory=list)
    error_code: str | None = None
    error_detail: str | None = None
    retryable: bool = False
    warnings: list[str] = field(default_factory=list)

    @property
    def is_success(self) -> bool:
        return self.error_code is None and bool(self.chunks)


@dataclass
class ParsedBundleResult:
    documents: list[ParsedDocument] = field(default_factory=list)

    @property
    def chunks(self) -> list[ParsedChunk]:
        return [chunk for document in self.documents for chunk in document.chunks]

    @property
    def successful_document_ids(self) -> set[str]:
        return {document.source_document_id for document in self.documents if document.is_success}

    @property
    def failed_document_ids(self) -> set[str]:
        return {document.source_document_id for document in self.documents if not document.is_success}


@dataclass(frozen=True)
class StoredParseResult:
    chunks_created: int
    parsed_assets_created: int
    parsed_document_ids: frozenset[str]
    failed_document_ids: frozenset[str]


@dataclass
class _ContentBlock:
    """Internal representation of a parsed content block."""
    type: str  # "heading", "paragraph", "table"
    content: str
    heading_level: int = 0
    heading_path: list[str] = field(default_factory=list)
    table_data: dict | None = None


@dataclass(frozen=True)
class _ExtractionOutcome:
    """Safe parser result used between extraction and durable persistence."""

    text: str
    error_code: str | None = None
    retryable: bool = False
    warnings: tuple[str, ...] = ()


class _ExtractedText(str):
    """String-compatible extraction result with non-secret parser diagnostics.

    Existing adapter callers and test monkeypatches expect ``_extract_text`` to
    return ``str``.  Keeping this as a ``str`` subclass preserves that boundary
    while letting the ingestion pipeline persist deterministic failure facts.
    """

    error_code: str | None
    retryable: bool
    warnings: tuple[str, ...]

    def __new__(
        cls,
        text: str,
        *,
        error_code: str | None = None,
        retryable: bool = False,
        warnings: tuple[str, ...] = (),
    ) -> "_ExtractedText":
        value = super().__new__(cls, text)
        value.error_code = error_code
        value.retryable = retryable
        value.warnings = warnings
        return value


def _download_from_minio(storage_key: str) -> bytes | None:
    """Download document bytes from MinIO using its durable storage key."""
    try:
        from app.adapters.storage import download_storage_key

        return download_storage_key(storage_key)
    except Exception as exc:
        logger.warning("MinIO download failed for %s: %s", storage_key, exc)
        return None


def _parser_error_detail(*, mime_type: str, error_code: str, retryable: bool) -> str:
    """Return a stable public parse diagnostic without internal exception data."""

    retry_flag = "true" if retryable else "false"
    return (
        f"parser={PARSER_NAME}@{PARSER_VERSION}; mime_type={mime_type}; "
        f"reason={error_code}; retryable={retry_flag}"
    )


def _extract_pdf_outcome(data: bytes) -> _ExtractionOutcome:
    """Extract PDF text and classify OCR availability truthfully.

    Native PDF text remains authoritative.  OCR is a narrow fallback for a
    page that contains virtually no selectable text, and it is deliberately
    visible in the normalized document through its page heading/locator.
    """
    try:
        import pymupdf

        doc = pymupdf.open(stream=data, filetype="pdf")
        pages: list[str] = []
        warnings: list[str] = []
        terminal_ocr_error: _ExtractionOutcome | None = None
        for page_number, page in enumerate(doc, start=1):
            text = page.get_text("text").strip()
            if _should_ocr_pdf_page(text):
                ocr = _extract_pdf_page_ocr_outcome(page, page_number)
                if ocr.text:
                    text = ocr.text
                elif ocr.error_code:
                    terminal_ocr_error = ocr
                    warnings.append(f"page_{page_number}:{ocr.error_code}")
            if text:
                pages.append(f"## Page {page_number}\n\n{text}".strip())
        doc.close()
        if pages:
            return _ExtractionOutcome(text="\n\n".join(pages), warnings=tuple(warnings))
        if terminal_ocr_error is not None:
            return terminal_ocr_error
        return _ExtractionOutcome(text="", error_code="no_extractable_text", retryable=False)
    except Exception as exc:
        logger.warning("PDF extraction failed: %s", exc)
        return _ExtractionOutcome(text="", error_code="pdf_parse_failed", retryable=False)


def _extract_pdf_text(data: bytes) -> str:
    """Compatibility wrapper for callers that only need normalized text."""

    return _extract_pdf_outcome(data).text


def _extract_docx_text(data: bytes) -> str:
    """Extract DOCX paragraphs and tables while retaining structural anchors."""
    try:
        from docx import Document
        from docx.table import Table
        from docx.text.paragraph import Paragraph

        doc = Document(io.BytesIO(data))
        lines: list[str] = []
        table_number = 0
        for child in doc.element.body.iterchildren():
            if child.tag.endswith("}p"):
                paragraph = Paragraph(child, doc)
                text = paragraph.text.strip()
                if not text:
                    continue
                heading_level = _docx_heading_level(paragraph.style.name if paragraph.style else "")
                lines.append(f"{'#' * heading_level} {text}" if heading_level else text)
                continue
            if not child.tag.endswith("}tbl"):
                continue
            table_number += 1
            table = Table(child, doc)
            table_lines = _docx_table_to_markdown(table)
            if table_lines:
                lines.extend((f"## Table {table_number}", *table_lines))
        return "\n\n".join(lines)
    except Exception as exc:
        logger.warning("DOCX extraction failed: %s", exc)
        return ""


def _extract_xlsx_text(data: bytes) -> str:
    """Render workbook sheets as bounded Markdown tables for retrieval."""
    try:
        from openpyxl import load_workbook

        workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        lines = ["# Workbook"]
        for worksheet in workbook.worksheets:
            rows = [
                [_table_cell_text(cell) for cell in row]
                for row in worksheet.iter_rows(values_only=True)
            ]
            table = _rows_to_markdown_table(rows)
            if table:
                lines.extend((f"## Sheet: {worksheet.title}", table))
        workbook.close()
        return "\n\n".join(lines)
    except Exception as exc:
        logger.warning("XLSX extraction failed: %s", exc)
        return ""


def _extract_csv_text(data: bytes) -> str:
    """Parse a CSV with safe encoding/delimiter fallbacks into one table."""
    decoded = ""
    for encoding in ("utf-8-sig", "gb18030", "latin-1"):
        try:
            decoded = data.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    if not decoded.strip():
        return ""
    try:
        sample = decoded[:4096]
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        except csv.Error:
            dialect = csv.excel
        rows = [[_table_cell_text(cell) for cell in row] for row in csv.reader(io.StringIO(decoded), dialect)]
        table = _rows_to_markdown_table(rows)
        return f"# CSV\n\n## Sheet: CSV\n\n{table}" if table else ""
    except (csv.Error, ValueError) as exc:
        logger.warning("CSV extraction failed: %s", exc)
        return ""


def _should_ocr_pdf_page(text: str) -> bool:
    return (
        os.getenv("DOCPILOT_OCR_ENABLED", "true").lower() in {"1", "true", "yes"}
        and len(re.sub(r"\s+", "", text)) < _OCR_TEXT_THRESHOLD
    )


def _extract_pdf_page_ocr_outcome(page, page_number: int) -> _ExtractionOutcome:
    """Run the local, explicitly installed Tesseract worker dependency.

    There is no silent cloud OCR fallback: a deployment without Tesseract is
    reported as an unavailable parser capability rather than leaking files to
    an unconfigured third party or pretending an image was understood.
    """
    binary = shutil.which("tesseract")
    if not binary:
        logger.info("OCR unavailable for PDF page %s: tesseract is not installed", page_number)
        return _ExtractionOutcome(text="", error_code="pdf_ocr_unavailable", retryable=False)
    languages = _available_ocr_languages(binary)
    if not languages:
        logger.warning("OCR unavailable for PDF page %s: no configured languages installed", page_number)
        return _ExtractionOutcome(text="", error_code="pdf_ocr_language_unavailable", retryable=False)
    try:
        import pymupdf

        pixmap = page.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)
    except Exception as exc:
        logger.warning("PDF rasterization failed for OCR page %s: %s", page_number, exc)
        return _ExtractionOutcome(text="", error_code="pdf_ocr_rasterization_failed", retryable=True)
    try:
        completed = subprocess.run(
            [binary, "stdin", "stdout", "-l", languages],
            input=pixmap.tobytes("png"),
            capture_output=True,
            check=False,
            timeout=45,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("OCR invocation failed for PDF page %s: %s", page_number, type(exc).__name__)
        return _ExtractionOutcome(text="", error_code="pdf_ocr_timeout", retryable=True)
    if completed.returncode != 0:
        logger.warning("OCR failed for PDF page %s: exit=%s", page_number, completed.returncode)
        return _ExtractionOutcome(text="", error_code="pdf_ocr_failed", retryable=True)
    text = completed.stdout.decode("utf-8", errors="replace").strip()
    return _ExtractionOutcome(
        text=text,
        error_code=None if text else "no_extractable_text",
        retryable=False,
    )


def _extract_pdf_page_ocr(page, page_number: int) -> str:
    """Compatibility wrapper for tests or adapters that only expect text."""

    return _extract_pdf_page_ocr_outcome(page, page_number).text


def _available_ocr_languages(binary: str) -> str | None:
    configured = [value for value in os.getenv("DOCPILOT_OCR_LANGS", "chi_sim+eng").split("+") if value]
    try:
        completed = subprocess.run(
            [binary, "--list-langs"],
            capture_output=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    available = {
        line.strip()
        for line in completed.stdout.decode("utf-8", errors="replace").splitlines()[1:]
        if line.strip()
    }
    selected = [language for language in configured if language in available]
    return "+".join(selected) if selected else None


def _docx_heading_level(style_name: str) -> int:
    match = re.search(r"heading\s*(\d+)", style_name, flags=re.IGNORECASE)
    return min(int(match.group(1)), 6) if match else 0


def _docx_table_to_markdown(table) -> list[str]:
    rows = [[_table_cell_text(cell.text) for cell in row.cells] for row in table.rows]
    table_text = _rows_to_markdown_table(rows)
    return table_text.splitlines() if table_text else []


def _table_cell_text(value: object) -> str:
    return "" if value is None else str(value).replace("|", "\\|").replace("\n", " ").strip()


def _rows_to_markdown_table(rows: list[list[str]]) -> str:
    meaningful = [row for row in rows if any(cell.strip() for cell in row)]
    if not meaningful:
        return ""
    width = max(len(row) for row in meaningful)
    normalized = [row + [""] * (width - len(row)) for row in meaningful]
    headers = [cell or f"Column {index}" for index, cell in enumerate(normalized[0], start=1)]
    lines = [f"| {' | '.join(headers)} |", f"| {' | '.join(['---'] * width)} |"]
    lines.extend(f"| {' | '.join(row)} |" for row in normalized[1:])
    return "\n".join(lines)


def _source_locator_from_heading_path(heading_path: list[str]) -> dict[str, object]:
    """Convert parser-generated structural headings into stable locators."""
    locator: dict[str, object] = {}
    for heading in heading_path:
        page_match = re.fullmatch(r"Page\s+(\d+)", heading, flags=re.IGNORECASE)
        if page_match:
            locator["page"] = int(page_match.group(1))
        sheet_match = re.fullmatch(r"Sheet:\s*(.+)", heading, flags=re.IGNORECASE)
        if sheet_match:
            locator["sheet"] = sheet_match.group(1).strip()[:120]
        table_match = re.fullmatch(r"Table\s+(\d+)", heading, flags=re.IGNORECASE)
        if table_match:
            locator["table"] = f"Table {table_match.group(1)}"
    return locator


def _table_locator_from_heading_path(heading_path: list[str]) -> str | None:
    locator = _source_locator_from_heading_path(heading_path)
    value = locator.get("table")
    return value if isinstance(value, str) else None


def _extract_text(storage_key: str, mime_type: str) -> str:
    """Route to the correct extractor based on MIME type.

    Downloads the file from MinIO first, then extracts text from bytes.
    Falls back to local file path if MinIO download fails.
    """
    data = _download_from_minio(storage_key)

    if data is not None:
        if mime_type == "application/pdf":
            outcome = _extract_pdf_outcome(data)
            return _ExtractedText(
                outcome.text,
                error_code=outcome.error_code,
                retryable=outcome.retryable,
                warnings=outcome.warnings,
            )
        if mime_type in (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/msword",
        ):
            text = _extract_docx_text(data)
            return _ExtractedText(text, error_code=None if text else "docx_parse_failed")
        if mime_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
            text = _extract_xlsx_text(data)
            return _ExtractedText(text, error_code=None if text else "xlsx_parse_failed")
        if mime_type == "text/csv":
            text = _extract_csv_text(data)
            return _ExtractedText(text, error_code=None if text else "csv_parse_failed")
        if mime_type not in {"text/plain", "text/markdown"}:
            return _ExtractedText("", error_code="unsupported_parser_mime", retryable=False)
        # Plain text
        try:
            return _ExtractedText(data.decode("utf-8", errors="replace"))
        except Exception as exc:
            logger.warning("Text decode failed for %s: %s", storage_key, exc)
            return _ExtractedText("", error_code="text_decode_failed", retryable=False)

    # Fallback: try reading as local file path
    try:
        with open(storage_key, encoding="utf-8", errors="replace") as f:
            return _ExtractedText(f.read())
    except Exception as exc:
        logger.warning("Text extraction failed for %s: %s", storage_key, exc)
        return _ExtractedText("", error_code="storage_unavailable", retryable=True)


# ── Heading & table detection helpers ──────────────────────────────────


def _heading_level(line: str) -> int:
    """Return markdown heading level (1-6) or 0 if not a heading."""
    m = re.match(r"^(#{1,6})\s+", line)
    return len(m.group(1)) if m else 0


def _is_table_row(line: str) -> bool:
    """True if the line looks like part of a markdown table."""
    s = line.strip()
    if not s:
        return False
    # Normal table row: |...|
    if s.startswith("|") and s.endswith("|"):
        return True
    # Separator row: |---|---|
    stripped = s.replace("|", "").replace("-", "").replace(":", "").strip()
    return not stripped


def _parse_table(lines: list[str]) -> dict:
    """Parse markdown table lines into {headers, rows}."""
    if not lines:
        return {"headers": [], "rows": []}
    headers = [c.strip() for c in lines[0].strip().strip("|").split("|")]
    rows: list[list[str]] = []
    for line in lines[2:]:
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        rows.append(cells)
    return {"headers": headers, "rows": rows}


# ── Document → content blocks ─────────────────────────────────────────


def _to_blocks(text: str) -> list[_ContentBlock]:
    """Tokenise plain text into a list of heading / paragraph / table blocks.

    Headings become natural section boundaries; tables are kept atomic.
    Each block carries its heading path so downstream retrieval knows the
    structural context of every chunk.
    """
    lines = text.split("\n")
    blocks: list[_ContentBlock] = []
    heading_path: list[str] = []
    i = 0

    while i < len(lines):
        line = lines[i]

        # Heading
        level = _heading_level(line)
        if level > 0:
            title = re.sub(r"^#+\s*", "", line).strip()
            heading_path = heading_path[: level - 1] + [title]
            blocks.append(_ContentBlock(
                type="heading",
                content=line,
                heading_level=level,
                heading_path=list(heading_path),
            ))
            i += 1
            continue

        # Table (greedily consume consecutive table lines)
        if _is_table_row(line):
            tbl: list[str] = []
            while i < len(lines) and _is_table_row(lines[i]):
                tbl.append(lines[i])
                i += 1
            blocks.append(_ContentBlock(
                type="table",
                content="\n".join(tbl),
                heading_path=list(heading_path),
                table_data=_parse_table(tbl),
            ))
            continue

        # Blank line → skip (acts as paragraph separator implicitly)
        if not line.strip():
            i += 1
            continue

        # Regular paragraph
        blocks.append(_ContentBlock(
            type="paragraph",
            content=line,
            heading_path=list(heading_path),
        ))
        i += 1

    return blocks


# ── Blocks → (content, metadata) chunks ───────────────────────────────


def _split_into_chunks(text: str, size: int = CHUNK_SIZE_CHARS) -> list[tuple[str, dict]]:
    """Split document text into hierarchical chunks with structured metadata.

    Returns a list of ``(content, metadata_dict)`` pairs.

    **Strategy**
    - Headings (``#`` / ``##`` / …) are **always** chunk boundaries.
    - Tables are kept as **atomic** units — never split across chunks.
    - Paragraphs accumulate until *size* is reached, then flush.
    - Each chunk records its ``heading_path`` so the retriever knows the
      structural context of every fragment.

    **Metadata keys**
    - ``chunk_type`` — ``"paragraphs"`` | ``"table"``
    - ``heading_path`` — ``["Section", "Sub-section"]``
    - ``heading_level`` — depth of the nearest heading (0 for orphans)
    - ``table_headers`` / ``table_row_count`` — only for table chunks
    """
    if not text.strip():
        return []

    blocks = _to_blocks(text)
    result: list[tuple[str, dict]] = []
    current_paras: list[str] = []
    current_len = 0
    current_heading: tuple[list[str], int] = ([], 0)
    current_source_locator: dict[str, object] = {}

    def _flush():
        nonlocal current_paras, current_len
        if not current_paras:
            return
        result.append((
            "\n\n".join(current_paras),
            {
                "chunk_type": "paragraphs",
                "heading_path": list(current_heading[0]),
                "heading_level": current_heading[1],
                "source_locator": dict(current_source_locator),
            },
        ))
        current_paras = []
        current_len = 0

    for blk in blocks:
        if blk.type == "heading":
            _flush()
            current_heading = (blk.heading_path, blk.heading_level)
            current_source_locator = _source_locator_from_heading_path(blk.heading_path)

        elif blk.type == "table":
            _flush()
            td = blk.table_data or {}
            result.append((
                blk.content,
                {
                    "chunk_type": "table",
                    "heading_path": list(current_heading[0]),
                    "heading_level": current_heading[1],
                    "table_headers": td.get("headers", []),
                    "table_row_count": len(td.get("rows", [])),
                    "source_locator": {
                        **current_source_locator,
                        "table": _table_locator_from_heading_path(current_heading[0]),
                    },
                },
            ))

        elif blk.type == "paragraph":
            txt = blk.content.strip()
            if not txt:
                continue
            # If adding this paragraph would exceed the cap, flush first
            if current_len + len(txt) > size and current_paras:
                _flush()
            current_paras.append(txt)
            current_len += len(txt)

    _flush()
    return result


# ── Public API ────────────────────────────────────────────────────────


def parse_bundle_documents(
    bundle_id: str,
    *,
    source_document_ids: set[str] | frozenset[str] | None = None,
) -> ParsedBundleResult:
    """Parse pending versions without mutating their durable state.

    Persisting a parse result is intentionally a separate transaction.  A
    Worker crash after parsing but before chunk persistence must leave a source
    document retryable rather than marking it as successfully parsed.
    """
    db = SessionLocal()
    try:
        bundle = db.get(Bundle, bundle_id)
        if bundle is None:
            return ParsedBundleResult()

        statement = select(SourceDocument).where(SourceDocument.bundle_id == bundle_id)
        if source_document_ids is not None:
            if not source_document_ids:
                return ParsedBundleResult()
            statement = statement.where(SourceDocument.id.in_(source_document_ids))
        documents = list(
            db.scalars(
                statement.order_by(SourceDocument.original_filename.asc(), SourceDocument.id.asc())
            ).all()
        )
        result = ParsedBundleResult()
        for doc in documents:
            if doc.parse_status == DocumentParseStatus.NOT_APPLICABLE.value:
                continue
            if doc.parse_status == DocumentParseStatus.PARSED.value:
                continue
            # ``_begin_ingest`` reserves an attempt before this pure parsing
            # stage runs.  Therefore the final allowed attempt is already at
            # the budget while its durable state is still ``parsing``.  Only
            # skip a prior terminal failure that exhausted its budget.
            if (
                doc.parse_attempt_count >= MAX_DOCUMENT_PARSE_ATTEMPTS
                and doc.parse_status != DocumentParseStatus.PARSING.value
            ):
                continue
            text = _extract_text(doc.storage_key, doc.mime_type)
            error_code = getattr(text, "error_code", None)
            # Adapters that return the legacy raw string shape cannot classify
            # an empty result. Treat that as transient until the durable retry
            # budget is exhausted; explicit parser diagnostics remain authoritative.
            retryable = bool(getattr(text, "retryable", error_code is None))
            warnings = list(getattr(text, "warnings", ()))
            if not text or not text.strip():
                classified_error = error_code or "no_extractable_text"
                logger.info("No text extracted from %s (%s)", doc.original_filename, classified_error)
                result.documents.append(
                    ParsedDocument(
                        source_document_id=doc.id,
                        source_checksum=doc.checksum,
                        version_number=doc.version_number,
                        error_code=classified_error,
                        error_detail=_parser_error_detail(
                            mime_type=doc.mime_type,
                            error_code=classified_error,
                            retryable=retryable,
                        ),
                        retryable=retryable,
                        warnings=warnings,
                    )
                )
                continue

            chunks: list[ParsedChunk] = []
            for local_index, (chunk_text, extra_meta) in enumerate(_split_into_chunks(text)):
                chunk_key = _stable_chunk_key(doc.id, doc.checksum, local_index)
                heading_path = extra_meta.get("heading_path") or []
                meta = {
                    "source_document_id": doc.id,
                    "source_checksum": doc.checksum,
                    "document_version": doc.version_number,
                    "mime_type": doc.mime_type,
                    "original_filename": doc.original_filename,
                    "parser_name": PARSER_NAME,
                    "parser_version": PARSER_VERSION,
                    "chunk_key": chunk_key,
                    "locator": {
                        "source_document_id": doc.id,
                        "chunk_index": local_index,
                        "heading": " > ".join(heading_path) if heading_path else None,
                        "table": "table" if extra_meta.get("chunk_type") == "table" else None,
                        "text_anchor": chunk_text[:240],
                        "source_checksum": doc.checksum,
                        "document_version": doc.version_number,
                    },
                }
                meta["locator"].update(extra_meta.get("source_locator") or {})
                meta.update(extra_meta)
                chunks.append(ParsedChunk(
                    chunk_index=local_index,
                    content=chunk_text,
                    chunk_key=chunk_key,
                    metadata=meta,
                ))
            if not chunks:
                result.documents.append(
                    ParsedDocument(
                        source_document_id=doc.id,
                        source_checksum=doc.checksum,
                        version_number=doc.version_number,
                        error_code="no_chunks_created",
                    )
                )
                continue
            result.documents.append(
                ParsedDocument(
                    source_document_id=doc.id,
                    source_checksum=doc.checksum,
                    version_number=doc.version_number,
                    normalized_text=text,
                    chunks=chunks,
                    warnings=warnings,
                )
            )

        return result
    finally:
        db.close()


def store_chunks(bundle_id: str, result: ParsedBundleResult) -> StoredParseResult:
    """Persist a bundle parse result atomically per Worker attempt.

    The source-document parse marker, canonical parsed asset, and retrieval
    chunks commit together.  Replaying the same result is idempotent through
    the durable ``chunk_key`` rather than a best-effort in-memory retry flag.
    """
    db = SessionLocal()
    try:
        bundle = db.get(Bundle, bundle_id)
        if bundle is None:
            return StoredParseResult(0, 0, frozenset(), frozenset())
        project_id = bundle.project_id
        now = datetime.now(UTC).replace(tzinfo=None)
        chunks_created = 0
        parsed_assets_created = 0
        parsed_document_ids: set[str] = set()
        failed_document_ids: set[str] = set()

        for document_result in result.documents:
            document = db.get(SourceDocument, document_result.source_document_id)
            if document is None or document.bundle_id != bundle_id:
                continue
            if not document_result.is_success:
                document.parse_status = DocumentParseStatus.FAILED.value
                document.parse_error_code = document_result.error_code or "parse_failed"
                document.parse_error_detail = document_result.error_detail or _parser_error_detail(
                    mime_type=document.mime_type,
                    error_code=document.parse_error_code,
                    retryable=document_result.retryable,
                )
                document.parse_retryable = document_result.retryable
                document.parser_name = PARSER_NAME
                document.parser_version = PARSER_VERSION
                document.parsed_at = None
                document.index_status = DocumentIndexStatus.PENDING.value
                document.index_error_code = None
                document.indexed_at = None
                failed_document_ids.add(document.id)
                continue

            chunk_keys = [chunk.chunk_key for chunk in document_result.chunks]
            existing_chunk_keys = set(
                db.scalars(
                    select(KnowledgeChunk.chunk_key).where(
                        KnowledgeChunk.source_document_id == document.id,
                        KnowledgeChunk.chunk_key.in_(chunk_keys),
                    )
                ).all()
            )
            for chunk in document_result.chunks:
                if chunk.chunk_key in existing_chunk_keys:
                    continue
                db.add(
                    KnowledgeChunk(
                        project_id=project_id,
                        source_document_id=document.id,
                        chunk_index=chunk.chunk_index,
                        chunk_key=chunk.chunk_key,
                        content=chunk.content,
                        metadata_json=chunk.metadata,
                        retrieval_text=normalize_retrieval_text(chunk.content),
                    )
                )
                chunks_created += 1

            asset = db.scalar(
                select(ParsedAsset).where(
                    ParsedAsset.source_document_id == document.id,
                    ParsedAsset.parser_name == PARSER_NAME,
                    ParsedAsset.parser_version == PARSER_VERSION,
                )
            )
            asset_content = {
                "normalized_text": document_result.normalized_text,
                "text_sha256": hashlib.sha256(document_result.normalized_text.encode("utf-8")).hexdigest(),
                "source_checksum": document_result.source_checksum,
                "document_version": document_result.version_number,
                "chunk_count": len(document_result.chunks),
                "parser": {"name": PARSER_NAME, "version": PARSER_VERSION},
                "parser_warnings": document_result.warnings,
            }
            asset_layout = {
                "chunk_count": len(document_result.chunks),
                "locators": [chunk.metadata["locator"] for chunk in document_result.chunks],
            }
            if asset is None:
                db.add(
                    ParsedAsset(
                        source_document_id=document.id,
                        parser_name=PARSER_NAME,
                        parser_version=PARSER_VERSION,
                        content_json=asset_content,
                        layout_json=asset_layout,
                    )
                )
                parsed_assets_created += 1
            else:
                asset.content_json = asset_content
                asset.layout_json = asset_layout

            document.parse_status = DocumentParseStatus.PARSED.value
            document.parser_name = PARSER_NAME
            document.parser_version = PARSER_VERSION
            document.parse_error_code = None
            document.parse_error_detail = None
            document.parse_retryable = True
            document.parsed_at = now
            document.index_status = DocumentIndexStatus.PENDING.value
            document.index_error_code = None
            document.indexed_at = None
            parsed_document_ids.add(document.id)
        db.commit()
        return StoredParseResult(
            chunks_created=chunks_created,
            parsed_assets_created=parsed_assets_created,
            parsed_document_ids=frozenset(parsed_document_ids),
            failed_document_ids=frozenset(failed_document_ids),
        )
    finally:
        db.close()


def _stable_chunk_key(source_document_id: str, source_checksum: str, chunk_index: int) -> str:
    material = f"{source_document_id}:{source_checksum}:{chunk_index}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()
