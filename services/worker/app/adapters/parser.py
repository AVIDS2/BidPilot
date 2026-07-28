"""Parser adapter for document ingestion.

Extracts text from PDF (PyMuPDF) and DOCX (python-docx), then splits into
hierarchical chunks with heading-aware boundaries, table detection, and
structured metadata for retrieval quality.
"""

import hashlib
import io
import logging
import re
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
PARSER_VERSION = "3.0"


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


def _download_from_minio(storage_key: str) -> bytes | None:
    """Download document bytes from MinIO using its durable storage key."""
    try:
        from app.adapters.storage import download_storage_key

        return download_storage_key(storage_key)
    except Exception as exc:
        logger.warning("MinIO download failed for %s: %s", storage_key, exc)
        return None


def _extract_pdf_text(data: bytes) -> str:
    """Extract text from a PDF file using PyMuPDF."""
    try:
        import pymupdf

        doc = pymupdf.open(stream=data, filetype="pdf")
        pages: list[str] = []
        for page in doc:
            pages.append(page.get_text())
        doc.close()
        return "\n\n".join(pages)
    except Exception as exc:
        logger.warning("PDF extraction failed: %s", exc)
        return ""


def _extract_docx_text(data: bytes) -> str:
    """Extract text from a DOCX file using python-docx."""
    try:
        from docx import Document

        doc = Document(io.BytesIO(data))
        return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except Exception as exc:
        logger.warning("DOCX extraction failed: %s", exc)
        return ""


def _extract_text(storage_key: str, mime_type: str) -> str:
    """Route to the correct extractor based on MIME type.

    Downloads the file from MinIO first, then extracts text from bytes.
    Falls back to local file path if MinIO download fails.
    """
    data = _download_from_minio(storage_key)

    if data is not None:
        if mime_type == "application/pdf":
            return _extract_pdf_text(data)
        if mime_type in (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/msword",
        ):
            return _extract_docx_text(data)
        # Plain text
        try:
            return data.decode("utf-8", errors="replace")
        except Exception as exc:
            logger.warning("Text decode failed for %s: %s", storage_key, exc)
            return ""

    # Fallback: try reading as local file path
    try:
        with open(storage_key, encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception as exc:
        logger.warning("Text extraction failed for %s: %s", storage_key, exc)
        return ""


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
            },
        ))
        current_paras = []
        current_len = 0

    for blk in blocks:
        if blk.type == "heading":
            _flush()
            current_heading = (blk.heading_path, blk.heading_level)

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


def parse_bundle_documents(bundle_id: str) -> ParsedBundleResult:
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

        documents = list(
            db.scalars(
                select(SourceDocument)
                .where(SourceDocument.bundle_id == bundle_id)
                .order_by(SourceDocument.original_filename.asc(), SourceDocument.id.asc())
            ).all()
        )
        result = ParsedBundleResult()
        for doc in documents:
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
            if not text or not text.strip():
                logger.info("No text extracted from %s", doc.original_filename)
                result.documents.append(
                    ParsedDocument(
                        source_document_id=doc.id,
                        source_checksum=doc.checksum,
                        version_number=doc.version_number,
                        error_code="no_extractable_text",
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
            document.parse_error_code = None
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
