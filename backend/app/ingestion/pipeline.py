import asyncio
from typing import Optional, Callable, Any
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
    on_progress: Optional[Callable[..., Any]] = None,
) -> int:
    """
    Run the full ingestion pipeline: parse, detect structure, chunk, embed, and store.
    Returns the number of chunks stored.
    """
    async def _notify(stage: str, progress: int, pages: int = 0, chunks: int = 0, embeddings: int = 0):
        if on_progress:
            try:
                res = on_progress(stage, progress, pages, chunks, embeddings)
                if asyncio.iscoroutine(res):
                    await res
            except Exception as e:
                logger.warning("Progress callback error", error=str(e), stage=stage)

    # ── Stage 1: Parse document ────────────────────────────────────────
    logger.info("Stage: extraction", document_id=document_id)
    await _notify("extraction", 12)
    loaded_doc = await asyncio.to_thread(parse_document, file_path)
    pages_count = len(loaded_doc.pages)
    await _notify("extraction", 25, pages=pages_count)

    # ── Stage 2: Detect structure & store pages/sections concurrently ──
    logger.info("Stage: structure_detection", document_id=document_id)
    await _notify("structure_detection", 32, pages=pages_count)
    structure = await asyncio.to_thread(detect_structure, loaded_doc)

    # Concurrently store sections and pages for lower I/O latency
    await asyncio.gather(
        store_sections(structure.sections, document_id, version_id),
        store_pages(loaded_doc.pages, document_id, version_id),
    )
    await _notify("structure_detection", 45, pages=pages_count)

    # ── Stage 3: Chunk ─────────────────────────────────────────────────
    logger.info("Stage: chunking", document_id=document_id)
    await _notify("chunking", 50, pages=pages_count)
    chunks = await asyncio.to_thread(chunk_document, loaded_doc, structure, document_id, version_id)
    chunks_count = len(chunks)
    await _notify("chunking", 60, pages=pages_count, chunks=chunks_count)

    # ── Stage 4: Generate embeddings with batch progress ───────────────
    logger.info("Stage: embedding", document_id=document_id, chunks=chunks_count)
    await _notify("embedding", 65, pages=pages_count, chunks=chunks_count)
    texts = [c.content for c in chunks]

    async def on_embed_batch_done(done: int, total: int):
        pct = 65 + int((done / max(1, total)) * 22)
        await _notify("embedding", pct, pages=pages_count, chunks=chunks_count, embeddings=done)

    embeddings = await embedding_service.aembed_texts_with_progress(
        texts,
        batch_size=64,
        on_batch_done=on_embed_batch_done,
    )
    await _notify("embedding", 88, pages=pages_count, chunks=chunks_count, embeddings=chunks_count)

    # ── Stage 5: Store chunks + embeddings ─────────────────────────────
    logger.info("Stage: indexing", document_id=document_id)
    await _notify("indexing", 92, pages=pages_count, chunks=chunks_count, embeddings=chunks_count)
    stored = await store_chunks_with_embeddings(
        chunks, embeddings, document_id, version_id, batch_size=150
    )

    # Invalidate cache since document chunks have changed
    invalidate_document_cache(document_id)

    await _notify("completed", 100, pages=pages_count, chunks=chunks_count, embeddings=stored)

    return stored
