import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from app.rag.embeddings import EmbeddingService
from app.rag.retriever import _VectorCache, prewarm_document_cache, _vector_cache
from app.ingestion.chunker import Chunk
from app.ingestion.loaders.pdf_loader import PDFLoader
from app.ingestion.indexer import store_chunk_batch, store_chunks_with_embeddings


def test_embedding_service_inference_and_conversion():
    service = EmbeddingService()
    # Test embedding single text
    vec = service.embed_text("Test parallel embedding")
    assert isinstance(vec, list)
    assert len(vec) == 384
    assert isinstance(vec[0], float)

    # Test batch embedding
    texts = [f"Text chunk {i}" for i in range(5)]
    vecs = service.embed_texts(texts, batch_size=2)
    assert len(vecs) == 5
    assert len(vecs[0]) == 384


def test_embedding_service_parallel_workers():
    service = EmbeddingService()
    texts = [f"Text chunk {i} with semantic content" for i in range(10)]
    vecs = service.embed_texts_parallel(texts, batch_size=2, max_workers=2)
    assert len(vecs) == 10
    assert len(vecs[0]) == 384


@pytest.mark.asyncio
async def test_embedding_service_pipelined():
    service = EmbeddingService()
    texts = [f"Text chunk {i}" for i in range(6)]
    emitted_batches = []

    async def on_batch(start_idx, end_idx, batch_vectors):
        emitted_batches.append((start_idx, end_idx, len(batch_vectors)))

    all_vecs = await service.aembed_texts_pipelined(
        texts,
        batch_size=2,
        on_batch_ready=on_batch,
    )
    assert len(all_vecs) == 6
    assert len(emitted_batches) == 3
    assert emitted_batches[0] == (0, 2, 2)
    assert emitted_batches[1] == (2, 4, 2)
    assert emitted_batches[2] == (4, 6, 2)


@pytest.mark.asyncio
async def test_vector_cache_prewarming():
    cache = _VectorCache(max_docs=5)
    doc_id = "test_doc_prewarm_123"

    chunks = [
        Chunk(
            chunk_id=f"c_{i}",
            content=f"Content for chunk {i}",
            metadata={"page": i + 1},
            token_count=10,
        )
        for i in range(3)
    ]
    embeddings = [[0.1 * (i + 1)] * 384 for i in range(3)]

    cache.set_document_data(doc_id, chunks, embeddings)

    assert doc_id in cache.cache
    matrix, retrieved_chunks = cache.cache[doc_id]
    assert matrix.shape == (3, 384)
    assert len(retrieved_chunks) == 3
    assert retrieved_chunks[0].chunk_id == "c_0"
    assert retrieved_chunks[0].content == "Content for chunk 0"


@pytest.mark.asyncio
async def test_store_chunk_batch():
    mock_col = MagicMock()
    mock_insert_result = MagicMock()
    mock_insert_result.inserted_ids = ["id_1", "id_2"]
    mock_col.insert_many = AsyncMock(return_value=mock_insert_result)

    with patch("app.ingestion.indexer.document_chunks_col", return_value=mock_col):
        chunks = [
            Chunk(chunk_id="c_1", content="t1", metadata={}, token_count=5),
            Chunk(chunk_id="c_2", content="t2", metadata={}, token_count=5),
        ]
        embeddings = [[0.1] * 384, [0.2] * 384]

        inserted = await store_chunk_batch(chunks, embeddings, "doc_1", "v_1")
        assert inserted == 2
        mock_col.insert_many.assert_called_once()


@pytest.mark.asyncio
async def test_store_chunks_with_embeddings_concurrent():
    mock_col = MagicMock()
    mock_insert_result = MagicMock()
    mock_insert_result.inserted_ids = ["id_1"]
    mock_col.insert_many = AsyncMock(return_value=mock_insert_result)

    with patch("app.ingestion.indexer.document_chunks_col", return_value=mock_col):
        chunks = [
            Chunk(chunk_id=f"c_{i}", content=f"t{i}", metadata={}, token_count=5)
            for i in range(4)
        ]
        embeddings = [[0.1] * 384 for _ in range(4)]

        # Batch size 2 -> 2 concurrent batch tasks
        inserted = await store_chunks_with_embeddings(
            chunks, embeddings, "doc_1", "v_1", batch_size=2
        )
        assert inserted == 2 * len(mock_insert_result.inserted_ids)
        assert mock_col.insert_many.call_count == 2


@pytest.mark.asyncio
async def test_run_ingestion_pipelined_flow():
    from app.ingestion.pipeline import run_ingestion
    from app.ingestion.loaders.base import LoadedDocument, DocumentPage
    from app.rag.retriever import _vector_cache

    doc_id = "test_doc_flow_999"
    version_id = "v_flow_1"

    # Mock parse_document
    fake_pages = [DocumentPage(content=f"Paragraph {i}\n\nDetailed explanation of page {i}", page_number=i+1) for i in range(4)]
    fake_doc = LoadedDocument(pages=fake_pages, total_pages=4, format="txt")

    mock_insert_result = MagicMock()
    mock_insert_result.inserted_ids = ["sec_1"]

    notifications = []
    async def progress_cb(stage, progress, pages=0, chunks=0, embeddings=0):
        notifications.append((stage, progress, pages, chunks, embeddings))

    with patch("app.ingestion.pipeline.parse_document", return_value=fake_doc), \
         patch("app.ingestion.pipeline.store_sections", AsyncMock(return_value=["sec_1"])), \
         patch("app.ingestion.pipeline.store_pages", AsyncMock(return_value=4)), \
         patch("app.ingestion.pipeline.store_chunk_batch", AsyncMock(return_value=2)):

        stored = await run_ingestion(doc_id, "dummy.txt", version_id, on_progress=progress_cb)
        assert stored > 0

        # Verify stages were called in sequence
        stages = [n[0] for n in notifications]
        assert "extraction" in stages
        assert "structure_detection" in stages
        assert "chunking" in stages
        assert "embedding" in stages
        assert "indexing" in stages
        assert "completed" in stages

        # Verify vector cache was pre-warmed for document
        assert doc_id in _vector_cache.cache
        matrix, cached_chunks = _vector_cache.cache[doc_id]
        assert len(cached_chunks) == len(matrix)
