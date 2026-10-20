import asyncio
from typing import Optional, Callable, Any, List
from app.ingestion.parser import parse_document
from app.ingestion.structure_detector import detect_structure
from app.ingestion.chunker import chunk_document
from app.ingestion.indexer import store_sections, store_chunk_batch
from app.ingestion.pages import store_pages
from app.rag.embeddings import embedding_service
from app.rag.retriever import prewarm_document_cache
import structlog

logger = structlog.get_logger()

async def run_ingestion(
    document_id: str,
    file_path: str,
    version_id: str,
    on_progress: Optional[Callable[..., Any]] = None,
) -> int:
    """
    Run high-performance parallel & pipelined ingestion:
    1. Parallel text extraction preserving page boundaries
    2. Concurrent structure detection & background pages/sections persistence
    3. Fast semantic chunking
    4. Pipelined multi-threaded embedding generation + concurrent MongoDB Atlas batch writes
    5. In-memory vector cache pre-warming for instant query response
    """
    async def _notify(stage: str, progress: int, pages: int = 0, chunks: int = 0, embeddings: int = 0):
        if on_progress:
            try:
                res = on_progress(stage, progress, pages, chunks, embeddings)
                if asyncio.iscoroutine(res):
                    await res
            except Exception as e:
                logger.warning("Progress callback error", error=str(e), stage=stage)

    # ── Stage 1: Parse document (multi-threaded extraction) ───────────
    logger.info("Stage: extraction", document_id=document_id)
    await _notify("extraction", 12)
    loaded_doc = await asyncio.to_thread(parse_document, file_path)
    pages_count = len(loaded_doc.pages)
    await _notify("extraction", 25, pages=pages_count)

    # ── Stage 2: Structure detection & non-blocking metadata storage ──
    logger.info("Stage: structure_detection", document_id=document_id)
    await _notify("structure_detection", 32, pages=pages_count)
    structure = await asyncio.to_thread(detect_structure, loaded_doc)

    # Launch sections and pages persistence in the background concurrently
    # This avoids blocking chunking and embedding on network round-trips
    meta_storage_task = asyncio.gather(
        store_sections(structure.sections, document_id, version_id),
        store_pages(loaded_doc.pages, document_id, version_id),
    )
    await _notify("structure_detection", 45, pages=pages_count)

    # ── Stage 3: Semantic Chunking ────────────────────────────────────
    logger.info("Stage: chunking", document_id=document_id)
    await _notify("chunking", 50, pages=pages_count)
    chunks = await asyncio.to_thread(chunk_document, loaded_doc, structure, document_id, version_id)
    chunks_count = len(chunks)
    await _notify("chunking", 60, pages=pages_count, chunks=chunks_count)

    if chunks_count == 0:
        await meta_storage_task
        prewarm_document_cache(document_id, [], [])
        await _notify("completed", 100, pages=pages_count, chunks=0, embeddings=0)
        return 0

    # ── Stage 4 & 5: Pipelined Parallel Embedding + Concurrent DB Writes ─
    logger.info("Stage: embedding", document_id=document_id, chunks=chunks_count)
    await _notify("embedding", 65, pages=pages_count, chunks=chunks_count)

    batch_size = 128
    chunk_batches = [chunks[i : i + batch_size] for i in range(0, chunks_count, batch_size)]
    
    all_embeddings: List[List[float]] = []
    store_tasks = []
    embeddings_done = 0

    for batch_idx, batch_chunks in enumerate(chunk_batches):
        batch_texts = [c.content for c in batch_chunks]
        
        # Compute embeddings in worker thread with PyTorch CPU optimization
        batch_vectors = await asyncio.to_thread(
            embedding_service.embed_texts,
            batch_texts,
            batch_size=batch_size,
        )
        all_embeddings.extend(batch_vectors)
        embeddings_done += len(batch_vectors)

        # Immediately pipeline database insertion in background without waiting
        task = asyncio.create_task(
            store_chunk_batch(batch_chunks, batch_vectors, document_id, version_id)
        )
        store_tasks.append(task)

        # Non-blocking progress update
        pct = 65 + int((embeddings_done / max(1, chunks_count)) * 23)
        await _notify("embedding", pct, pages=pages_count, chunks=chunks_count, embeddings=embeddings_done)

    # ── Await completion of all pipelined writes & metadata storage ──
    logger.info("Stage: indexing", document_id=document_id)
    await _notify("indexing", 92, pages=pages_count, chunks=chunks_count, embeddings=chunks_count)

    batch_counts = await asyncio.gather(*store_tasks)
    stored = sum(batch_counts)

    # Ensure background pages & sections have finished persisting
    await meta_storage_task
    await _notify("indexing", 97, pages=pages_count, chunks=chunks_count, embeddings=stored)

    # ── Pre-warm Vector Cache for instant query retrieval latency ─────
    prewarm_document_cache(document_id, chunks, all_embeddings)

    await _notify("completed", 100, pages=pages_count, chunks=chunks_count, embeddings=stored)
    logger.info("Document ingestion fully completed", document_id=document_id, stored=stored)

    return stored
