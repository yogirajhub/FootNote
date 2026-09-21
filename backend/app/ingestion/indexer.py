"""
Indexer — stores processed chunks and their embeddings into MongoDB.
Also creates the vector search index when needed.
"""
from datetime import datetime, timezone
from typing import List, Optional, Callable
from app.ingestion.chunker import Chunk
from app.db.mongodb import document_chunks_col, document_sections_col
from app.ingestion.structure_detector import DetectedStructure, DocumentSection
import structlog

logger = structlog.get_logger()


async def store_sections(
    sections: List[DocumentSection],
    document_id: str,
    document_version_id: str,
) -> List[str]:
    """Persist detected sections to MongoDB. Returns list of inserted IDs."""
    if not sections:
        return []

    col = document_sections_col()
    docs = [
        {
            "document_id": document_id,
            "document_version_id": document_version_id,
            "title": s.title,
            "level": s.level,
            "page_number": s.page_number,
            "parent_title": s.parent_title,
            "order": s.order,
            "created_at": datetime.now(timezone.utc),
        }
        for s in sections
    ]
    result = await col.insert_many(docs)
    logger.info("Sections stored", count=len(result.inserted_ids), document_id=document_id)
    return [str(i) for i in result.inserted_ids]


async def store_chunks_with_embeddings(
    chunks: List[Chunk],
    embeddings: List[List[float]],
    document_id: str,
    document_version_id: str,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> int:
    """
    Store chunks + embeddings in MongoDB document_chunks collection.
    Returns number of chunks stored.
    """
    if not chunks:
        return 0

    col = document_chunks_col()
    batch_size = 50
    stored = 0

    for i in range(0, len(chunks), batch_size):
        batch_chunks = chunks[i: i + batch_size]
        batch_embeddings = embeddings[i: i + batch_size]

        docs = []
        for chunk, embedding in zip(batch_chunks, batch_embeddings):
            docs.append({
                "_id": chunk.chunk_id,
                "document_id": document_id,
                "document_version_id": document_version_id,
                "content": chunk.content,
                "metadata": chunk.metadata,
                "token_count": chunk.token_count,
                "embedding": embedding,
                "previous_chunk_id": chunk.previous_chunk_id,
                "next_chunk_id": chunk.next_chunk_id,
                "parent_chunk_id": chunk.parent_chunk_id,
                "created_at": datetime.now(timezone.utc),
            })

        await col.insert_many(docs, ordered=False)
        stored += len(docs)

        if progress_callback:
            progress_callback(stored, len(chunks))

        logger.debug("Batch stored", batch=i // batch_size + 1, stored=stored)

    logger.info("All chunks stored", total=stored, document_id=document_id)
    return stored


async def delete_document_chunks(document_id: str) -> int:
    """Remove all chunks for a document (used on delete/reprocess)."""
    col = document_chunks_col()
    result = await col.delete_many({"document_id": document_id})
    logger.info("Chunks deleted", document_id=document_id, count=result.deleted_count)
    return result.deleted_count


async def delete_document_sections(document_id: str) -> int:
    """Remove all sections for a document."""
    col = document_sections_col()
    result = await col.delete_many({"document_id": document_id})
    return result.deleted_count
