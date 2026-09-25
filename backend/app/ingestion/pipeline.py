import asyncio
from typing import Optional, Callable
from app.ingestion.parser import parse_document
from app.ingestion.structure_detector import detect_structure
from app.ingestion.chunker import chunk_document
from app.ingestion.indexer import store_sections, store_chunks_with_embeddings
from app.ingestion.pages import store_pages
from app.rag.embeddings import embedding_service
from app.rag.retriever import invalidate_document_cache
import structlog

logger = structlog.get_logger()

async def run_ingestion(
    document_id: str,
    file_path: str,
    version_id: str,
    on_progress: Optional[Callable[[str, int], None]] = None,
) -> int:
    """
    Run the full ingestion pipeline: parse, detect structure, chunk, embed, and store.
    Returns the number of chunks stored.
    """
    if on_progress:
        on_progress("extraction", 5)

    # ── Stage 1: Parse document ────────────────────────────────────────
    logger.info("Stage: extraction", document_id=document_id)
    loaded_doc = await asyncio.to_thread(parse_document, file_path)
    
    if on_progress:
        on_progress("structure_detection", 20)

    # ── Stage 2: Detect structure ──────────────────────────────────────
    logger.info("Stage: structure_detection", document_id=document_id)
    structure = await asyncio.to_thread(detect_structure, loaded_doc)
    await store_sections(structure.sections, document_id, version_id)
    
    # Also store pages
    await store_pages(loaded_doc.pages, document_id, version_id)
    
    if on_progress:
        on_progress("chunking", 35)

    # ── Stage 3: Chunk ─────────────────────────────────────────────────
    logger.info("Stage: chunking", document_id=document_id)
    chunks = await asyncio.to_thread(chunk_document, loaded_doc, structure, document_id, version_id)
    
    if on_progress:
        on_progress("embedding", 50)

    # ── Stage 4: Generate embeddings ───────────────────────────────────
    logger.info("Stage: embedding", document_id=document_id, chunks=len(chunks))
    texts = [c.content for c in chunks]
    embeddings = await embedding_service.aembed_texts(texts, batch_size=32)
    
    if on_progress:
        on_progress("indexing", 80)

    # ── Stage 5: Store chunks + embeddings ─────────────────────────────
    logger.info("Stage: indexing", document_id=document_id)
    stored = await store_chunks_with_embeddings(
        chunks, embeddings, document_id, version_id
    )

    # Invalidate cache since document chunks have changed
    invalidate_document_cache(document_id)

    if on_progress:
        on_progress("completed", 100)

    return stored
