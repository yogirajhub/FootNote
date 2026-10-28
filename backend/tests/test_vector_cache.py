import pytest
import numpy as np
from app.rag.retriever import _VectorCache, _numpy_search, prewarm_document_cache, RetrievedChunk
from app.config.settings import settings

@pytest.mark.asyncio
async def test_numpy_search_score_normalization():
    """Verify that numpy search converts raw cosine [-1, 1] to Atlas [0, 1] scale."""
    doc_id = "test_doc_norm_123"
    
    # 2 synthetic chunks:
    # Chunk 1: identical vector to query -> raw cosine = 1.0 -> normalized = 1.0
    # Chunk 2: orthogonal vector to query -> raw cosine = 0.0 -> normalized = 0.5
    # Chunk 3: opposite vector to query -> raw cosine = -1.0 -> normalized = 0.0
    chunks = [
        {"_id": "c1", "document_id": doc_id, "content": "chunk 1", "metadata": {}},
        {"_id": "c2", "document_id": doc_id, "content": "chunk 2", "metadata": {}},
        {"_id": "c3", "document_id": doc_id, "content": "chunk 3", "metadata": {}},
    ]
    
    dim = settings.embedding_dimensions
    v1 = [1.0] + [0.0] * (dim - 1)
    v2 = [0.0, 1.0] + [0.0] * (dim - 2)
    v3 = [-1.0] + [0.0] * (dim - 1)
    
    prewarm_document_cache(doc_id, chunks, [v1, v2, v3])
    
    query_vec = np.array([1.0] + [0.0] * (dim - 1), dtype=np.float32)
    results = await _numpy_search(query_vec, doc_id, top_k=3)
    
    assert len(results) == 3
    # Check that scores are on 0-1 scale
    assert abs(results[0].score - 1.0) < 1e-5
    assert abs(results[1].score - 0.5) < 1e-5
    assert abs(results[2].score - 0.0) < 1e-5
    
    # And check that orthogonal vector (cosine=0.0 -> normalized=0.5) passes min_relevance=0.15
    assert results[1].score >= settings.min_relevance

