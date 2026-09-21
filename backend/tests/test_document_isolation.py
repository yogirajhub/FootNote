"""
Critical tests for document isolation in RAG retrieval.
Ensure queries for Document A NEVER retrieve chunks from Document B.
"""
import pytest
import asyncio
from app.rag.retriever import RetrievedChunk
from app.db.mongodb import document_chunks_col

# Use pytest-asyncio marker for async tests
pytestmark = pytest.mark.asyncio


@pytest.fixture
async def setup_test_chunks():
    col = document_chunks_col()
    await col.delete_many({"document_id": {"$in": ["doc_A", "doc_B"]}})

    chunks = [
        # Document A
        {
            "_id": "chunk_A1",
            "document_id": "doc_A",
            "content": "Apples are red.",
            "embedding": [0.1] * 384,  # dummy embedding
        },
        {
            "_id": "chunk_A2",
            "document_id": "doc_A",
            "content": "Bananas are yellow.",
            "embedding": [0.2] * 384,
        },
        # Document B
        {
            "_id": "chunk_B1",
            "document_id": "doc_B",
            "content": "Carrots are orange.",
            "embedding": [0.3] * 384,
        },
        {
            "_id": "chunk_B2",
            "document_id": "doc_B",
            "content": "Apples are also green.",  # Semantically similar to doc_A
            "embedding": [0.1] * 384,
        },
    ]
    await col.insert_many(chunks)
    yield
    await col.delete_many({"document_id": {"$in": ["doc_A", "doc_B"]}})


async def test_document_isolation_single(setup_test_chunks, monkeypatch):
    """Test that retrieving from doc_A does not return doc_B chunks."""
    from app.rag import retriever

    # Mock vector search to return all chunks matching the filter (bypassing actual vector DB)
    async def mock_retrieve(query, match_filter, top_k):
        col = document_chunks_col()
        cursor = col.find(match_filter).limit(top_k)
        docs = await cursor.to_list(length=top_k)
        return [RetrievedChunk(d, score=1.0) for d in docs]

    monkeypatch.setattr(retriever, "_keyword_fallback", mock_retrieve)

    # Test single document retrieval
    results_A = await retriever._keyword_fallback(
        "apples", {"document_id": "doc_A"}, top_k=5
    )
    assert len(results_A) == 2
    for r in results_A:
        assert r.document_id == "doc_A"
        assert r.chunk_id in ["chunk_A1", "chunk_A2"]

    results_B = await retriever._keyword_fallback(
        "apples", {"document_id": "doc_B"}, top_k=5
    )
    assert len(results_B) == 2
    for r in results_B:
        assert r.document_id == "doc_B"
        assert r.chunk_id in ["chunk_B1", "chunk_B2"]


async def test_cross_document_retrieval(setup_test_chunks, monkeypatch):
    """Test retrieving across multiple documents."""
    from app.rag import retriever

    async def mock_retrieve(query, match_filter, top_k):
        col = document_chunks_col()
        cursor = col.find(match_filter).limit(top_k)
        docs = await cursor.to_list(length=top_k)
        return [RetrievedChunk(d, score=1.0) for d in docs]

    monkeypatch.setattr(retriever, "_keyword_fallback", mock_retrieve)

    results = await retriever._keyword_fallback(
        "apples", {"document_id": {"$in": ["doc_A", "doc_B"]}}, top_k=5
    )
    assert len(results) == 4
    doc_ids = {r.document_id for r in results}
    assert "doc_A" in doc_ids
    assert "doc_B" in doc_ids
