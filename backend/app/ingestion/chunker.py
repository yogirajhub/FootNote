"""
Structure-aware semantic chunker.

Strategy:
1. Walk through document pages with detected sections.
2. Assign each page to its section context.
3. Split page content into paragraph-level chunks.
4. Merge small paragraphs and split large ones by token count.
5. Attach rich metadata to every chunk.
6. Link chunks: previous_chunk_id, next_chunk_id, parent_chunk_id.
"""
import re
import uuid
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from app.ingestion.loaders.base import LoadedDocument, DocumentPage
from app.ingestion.structure_detector import DetectedStructure, DocumentSection
from app.config.settings import settings
import structlog

logger = structlog.get_logger()


@dataclass
class Chunk:
    chunk_id: str
    content: str
    metadata: Dict[str, Any]
    token_count: int
    parent_chunk_id: Optional[str] = None
    previous_chunk_id: Optional[str] = None
    next_chunk_id: Optional[str] = None


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token."""
    return max(1, len(text) // 4)


def _split_into_paragraphs(text: str) -> List[str]:
    """Split text into paragraphs by double newline."""
    paragraphs = re.split(r"\n{2,}", text)
    return [p.strip() for p in paragraphs if p.strip()]


def _get_section_for_page(
    page: DocumentPage,
    structure: DetectedStructure,
) -> Optional[DocumentSection]:
    """Find the most recent section that starts at or before this page."""
    if not structure.sections:
        return None
    candidates = [
        s for s in structure.sections
        if s.page_number is not None and s.page_number <= (page.page_number or 0)
    ]
    return candidates[-1] if candidates else None


def chunk_document(
    doc: LoadedDocument,
    structure: DetectedStructure,
    document_id: str,
    document_version_id: str,
    chunk_size: Optional[int] = None,
    chunk_overlap: Optional[int] = None,
) -> List[Chunk]:
    """
    Produce structure-aware chunks from a LoadedDocument.
    Returns a flat list of Chunk objects with full metadata.
    """
    max_tokens = chunk_size or settings.chunk_size
    overlap_tokens = chunk_overlap or settings.chunk_overlap

    chunks: List[Chunk] = []
    previous_chunk_id: Optional[str] = None

    for page in doc.pages:
        section = _get_section_for_page(page, structure)

        base_metadata: Dict[str, Any] = {
            "document_id": document_id,
            "document_version_id": document_version_id,
            "page": page.page_number,
        }
        if section:
            if section.level == 1:
                base_metadata["part"] = section.title
            elif section.level == 2:
                base_metadata["chapter"] = section.title
                if section.parent_title:
                    base_metadata["part"] = section.parent_title
            elif section.level == 3:
                base_metadata["section"] = section.title
                if section.parent_title:
                    base_metadata["chapter"] = section.parent_title

        # Split page into paragraphs
        paragraphs = _split_into_paragraphs(page.content)

        # Merge paragraphs into chunks respecting max_tokens
        buffer = []
        buffer_tokens = 0

        for para_idx, para in enumerate(paragraphs):
            para_tokens = _estimate_tokens(para)

            # If adding this para would exceed limit, flush buffer first
            if buffer and buffer_tokens + para_tokens > max_tokens:
                chunk_id = f"chunk_{uuid.uuid4().hex[:16]}"
                chunk_content = "\n\n".join(buffer)
                meta = {
                    **base_metadata,
                    "paragraph": para_idx,
                    "chunk_index": len(chunks),
                }
                chunk = Chunk(
                    chunk_id=chunk_id,
                    content=chunk_content,
                    metadata=meta,
                    token_count=buffer_tokens,
                    previous_chunk_id=previous_chunk_id,
                )
                chunks.append(chunk)
                previous_chunk_id = chunk_id

                # Overlap: keep last N tokens worth of text
                overlap_buf = _trim_to_tokens(buffer, overlap_tokens)
                buffer = overlap_buf
                buffer_tokens = sum(_estimate_tokens(b) for b in buffer)

            # If a single paragraph is too large, split it by sentences
            if para_tokens > max_tokens:
                sentences = re.split(r"(?<=[.!?])\s+", para)
                sent_buffer: List[str] = []
                sent_tokens = 0
                for sent in sentences:
                    st = _estimate_tokens(sent)
                    if sent_buffer and sent_tokens + st > max_tokens:
                        chunk_id = f"chunk_{uuid.uuid4().hex[:16]}"
                        chunk_content = " ".join(sent_buffer)
                        meta = {
                            **base_metadata,
                            "paragraph": para_idx,
                            "chunk_index": len(chunks),
                        }
                        chunk = Chunk(
                            chunk_id=chunk_id,
                            content=chunk_content,
                            metadata=meta,
                            token_count=sent_tokens,
                            previous_chunk_id=previous_chunk_id,
                        )
                        chunks.append(chunk)
                        previous_chunk_id = chunk_id
                        sent_buffer = []
                        sent_tokens = 0
                    sent_buffer.append(sent)
                    sent_tokens += st
                if sent_buffer:
                    buffer.extend(sent_buffer)
                    buffer_tokens += sent_tokens
            else:
                buffer.append(para)
                buffer_tokens += para_tokens

        # Flush remaining buffer
        if buffer:
            chunk_id = f"chunk_{uuid.uuid4().hex[:16]}"
            chunk_content = "\n\n".join(buffer)
            meta = {
                **base_metadata,
                "chunk_index": len(chunks),
            }
            chunk = Chunk(
                chunk_id=chunk_id,
                content=chunk_content,
                metadata=meta,
                token_count=buffer_tokens,
                previous_chunk_id=previous_chunk_id,
            )
            chunks.append(chunk)
            previous_chunk_id = chunk_id

    # Link next_chunk_id forward
    for i in range(len(chunks) - 1):
        chunks[i].next_chunk_id = chunks[i + 1].chunk_id

    logger.info("Chunking complete", total_chunks=len(chunks), document_id=document_id)
    return chunks


def _trim_to_tokens(paragraphs: List[str], max_tokens: int) -> List[str]:
    """Return the tail of paragraphs list that fits within max_tokens."""
    result = []
    tokens = 0
    for para in reversed(paragraphs):
        t = _estimate_tokens(para)
        if tokens + t > max_tokens:
            break
        result.insert(0, para)
        tokens += t
    return result
