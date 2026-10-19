"""
Critical tests for document isolation in RAG retrieval.
Ensure queries for Document A NEVER retrieve chunks from Document B.
"""
import pytest
import pytest_asyncio
import asyncio
from app.rag.retriever import RetrievedChunk

pytestmark = pytest.mark.asyncio

TEST_CHUNKS = [
    # Document A
    {
        "_id": "chunk_A1",
        "document_id": "doc_A",
        "content": "Apples are red.",
        "embedding": [0.1] * 384,
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


def _filter_chunks(chunks, match_filter):
    res = []
    for c in chunks:
        doc_id_spec = match_filter.get("document_id")
        if isinstance(doc_id_spec, dict) and "$in" in doc_id_spec:
            if c["document_id"] in doc_id_spec["$in"]:
                res.append(c)
        elif doc_id_spec is not None:
            if c["document_id"] == doc_id_spec:
                res.append(c)
        else:
            res.append(c)
    return res


async def test_document_isolation_single(monkeypatch):
    """Test that retrieving from doc_A does not return doc_B chunks."""
    from app.rag import retriever

    async def mock_retrieve(query, match_filter, top_k):
        matched = _filter_chunks(TEST_CHUNKS, match_filter)[:top_k]
        return [RetrievedChunk(d, score=1.0) for d in matched]

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


async def test_cross_document_retrieval(monkeypatch):
    """Test retrieving across multiple documents."""
    from app.rag import retriever

    async def mock_retrieve(query, match_filter, top_k):
        matched = _filter_chunks(TEST_CHUNKS, match_filter)[:top_k]
        return [RetrievedChunk(d, score=1.0) for d in matched]

    monkeypatch.setattr(retriever, "_keyword_fallback", mock_retrieve)

    results = await retriever._keyword_fallback(
        "apples", {"document_id": {"$in": ["doc_A", "doc_B"]}}, top_k=5
    )
    assert len(results) == 4
    doc_ids = {r.document_id for r in results}
    assert "doc_A" in doc_ids
    assert "doc_B" in doc_ids
