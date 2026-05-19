"""Parser adapter for document ingestion.

Extracts text from PDF (PyMuPDF) and DOCX (python-docx), splits into
overlapping chunks, and persists as KnowledgeChunk rows.
"""

import io
import logging
import re
from dataclasses import dataclass, field

from app.db import SessionLocal
from app.models import Bundle, KnowledgeChunk, SourceDocument

logger = logging.getLogger(__name__)

CHUNK_SIZE_CHARS = 1200
CHUNK_OVERLAP_CHARS = 200


@dataclass
class ParsedChunk:
    chunk_index: int
    content: str
    metadata: dict = field(default_factory=dict)


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


def _split_into_chunks(text: str, size: int = CHUNK_SIZE_CHARS, overlap: int = CHUNK_OVERLAP_CHARS) -> list[str]:
    """Split text into overlapping chunks of roughly `size` characters."""
    if not text.strip():
        return []
    # Split on paragraph boundaries when possible
    paragraphs = re.split(r"\n{2,}", text)
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if current_len + len(para) > size and current:
            chunks.append("\n\n".join(current))
            # Keep overlap
            overlap_text = "\n\n".join(current)
            if len(overlap_text) > overlap:
                overlap_text = overlap_text[-overlap:]
            current = [overlap_text]
            current_len = len(overlap_text)
        current.append(para)
        current_len += len(para)

    if current:
        chunks.append("\n\n".join(current))

    return chunks


def parse_bundle_documents(bundle_id: str) -> list[ParsedChunk]:
    """Parse all source documents in a bundle and return chunks.

    Extracts text from each document, splits into overlapping chunks,
    and records source metadata.
    """
    db = SessionLocal()
    try:
        bundle = db.get(Bundle, bundle_id)
        if bundle is None:
            return []

        all_chunks: list[ParsedChunk] = []
        global_idx = 0

        for doc in bundle.source_documents:
            text = _extract_text(doc.storage_key, doc.mime_type)
            if not text.strip():
                logger.info("No text extracted from %s", doc.original_filename)
                continue

            doc_chunks = _split_into_chunks(text)
            for i, chunk_text in enumerate(doc_chunks):
                all_chunks.append(ParsedChunk(
                    chunk_index=global_idx,
                    content=chunk_text,
                    metadata={
                        "source_document_id": doc.id,
                        "mime_type": doc.mime_type,
                        "original_filename": doc.original_filename,
                        "local_chunk_index": i,
                        "parser_name": "docpilot-text-v1",
                    },
                ))
                global_idx += 1

            # Update parse status
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
            )
            db.add(kc)
            count += 1
        db.commit()
        return count
    finally:
        db.close()
