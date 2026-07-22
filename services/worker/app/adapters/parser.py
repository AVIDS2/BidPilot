"""Parser adapter for document ingestion.

Extracts text from PDF (PyMuPDF) and DOCX (python-docx), then splits into
hierarchical chunks with heading-aware boundaries, table detection, and
structured metadata for retrieval quality.
"""

import io
import logging
import re
from dataclasses import dataclass, field

from app.db import SessionLocal
from app.models import Bundle, KnowledgeChunk, SourceDocument
from app.retrieval.normalization import normalize_retrieval_text
from sqlalchemy import func, select

logger = logging.getLogger(__name__)

CHUNK_SIZE_CHARS = 1500   # Slightly larger to keep sections together
MAX_SECTION_CHARS = 3000  # Hard cap for a single section before sub-splitting


@dataclass
class ParsedChunk:
    chunk_index: int
    content: str
    metadata: dict = field(default_factory=dict)


@dataclass
class _ContentBlock:
    """Internal representation of a parsed content block."""
    type: str  # "heading", "paragraph", "table"
    content: str
    heading_level: int = 0
    heading_path: list[str] = field(default_factory=list)
    table_data: dict | None = None


def _download_from_minio(storage_key: str) -> bytes | None:
    """Download document bytes from MinIO using the storage_key.

    storage_key format: ``{project_id}/{object_name}`` or just ``{object_name}``.
    """
    try:
        from app.adapters.storage import download_document

        parts = storage_key.split("/", 1)
        if len(parts) == 2:
            project_id, object_name = parts
            return download_document(project_id, object_name)
        return None
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


def parse_bundle_documents(bundle_id: str) -> list[ParsedChunk]:
    """Parse all source documents in a bundle and return hierarchical chunks.

    Extracts text from each document, splits into heading-aware chunks,
    detects tables, and records structural metadata (heading path, etc.)
    so the retriever can rank by context depth.
    """
    db = SessionLocal()
    try:
        bundle = db.get(Bundle, bundle_id)
        if bundle is None:
            return []

        all_chunks: list[ParsedChunk] = []
        existing_max_index = db.scalar(
            select(func.max(KnowledgeChunk.chunk_index))
            .join(SourceDocument, SourceDocument.id == KnowledgeChunk.source_document_id)
            .where(SourceDocument.bundle_id == bundle_id)
        )
        global_idx = 0 if existing_max_index is None else int(existing_max_index) + 1

        for doc in bundle.source_documents:
            if doc.parse_status == "parsed":
                continue
            text = _extract_text(doc.storage_key, doc.mime_type)
            if not text.strip():
                logger.info("No text extracted from %s", doc.original_filename)
                continue

            for chunk_text, extra_meta in _split_into_chunks(text):
                meta = {
                    "source_document_id": doc.id,
                    "mime_type": doc.mime_type,
                    "original_filename": doc.original_filename,
                    "parser_name": "docpilot-hierarchical-v2",
                }
                meta.update(extra_meta)
                all_chunks.append(ParsedChunk(
                    chunk_index=global_idx,
                    content=chunk_text,
                    metadata=meta,
                ))
                global_idx += 1

            doc.parse_status = "parsed"
            db.commit()

        return all_chunks
    finally:
        db.close()


def store_chunks(bundle_id: str, chunks: list[ParsedChunk]) -> int:
    """Persist parsed chunks as KnowledgeChunk rows."""
    db = SessionLocal()
    try:
        bundle = db.get(Bundle, bundle_id)
        if bundle is None:
            return 0
        project_id = bundle.project_id
        count = 0
        for chunk in chunks:
            source_doc_id = chunk.metadata.get("source_document_id", "")
            kc = KnowledgeChunk(
                project_id=project_id,
                source_document_id=source_doc_id,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                metadata_json=chunk.metadata,
                retrieval_text=normalize_retrieval_text(chunk.content),
            )
            db.add(kc)
            count += 1
        db.commit()
        return count
    finally:
        db.close()
