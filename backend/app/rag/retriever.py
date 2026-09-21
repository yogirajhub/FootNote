"""
Retriever — MongoDB vector search + keyword fallback.

Retrieval is always document-scoped by default.
Cross-document mode can be enabled by passing multiple document_ids.
"""
from typing import List, Optional, Dict, Any
from app.db.mongodb import document_chunks_col
from app.rag.embeddings import embedding_service
from app.config.settings import settings
import structlog

logger = structlog.get_logger()


class RetrievedChunk:
    def __init__(self, data: dict, score: float = 0.0):
        self.chunk_id: str = str(data.get("_id", ""))
        self.document_id: str = data.get("document_id", "")
        self.content: str = data.get("content", "")
        self.metadata: Dict[str, Any] = data.get("metadata", {})
        self.score: float = score
        self.previous_chunk_id: Optional[str] = data.get("previous_chunk_id")
        self.next_chunk_id: Optional[str] = data.get("next_chunk_id")


async def retrieve(
    query: str,
    document_id: str,
    top_k: Optional[int] = None,
    document_ids: Optional[List[str]] = None,  # for cross-doc mode
    chapter_filter: Optional[str] = None,
    section_filter: Optional[str] = None,
) -> List[RetrievedChunk]:
    """
    Retrieve relevant chunks using MongoDB vector search.

    By default, restricts to a single document_id (document-scoped).
    If document_ids is provided, searches across those documents only.
    """
    k = top_k or settings.retrieval_top_k
    query_embedding = embedding_service.embed_text(query)

    # Build match filter — ALWAYS include document scope
    match_filter: Dict[str, Any] = {}
    if document_ids:
        match_filter["document_id"] = {"$in": document_ids}
    else:
        match_filter["document_id"] = document_id

    if chapter_filter:
        match_filter["metadata.chapter"] = {"$regex": chapter_filter, "$options": "i"}
    if section_filter:
        match_filter["metadata.section"] = {"$regex": section_filter, "$options": "i"}

    # MongoDB vector search pipeline
    pipeline = [
        {
            "$vectorSearch": {
                "index": settings.vector_index_name,
                "path": "embedding",
                "queryVector": query_embedding,
                "numCandidates": k * 10,
                "limit": k,
                "filter": match_filter,
            }
        },
        {
            "$project": {
                "_id": 1,
                "document_id": 1,
                "content": 1,
                "metadata": 1,
                "previous_chunk_id": 1,
                "next_chunk_id": 1,
                "score": {"$meta": "vectorSearchScore"},
            }
        },
    ]

    col = document_chunks_col()
    try:
        cursor = col.aggregate(pipeline)
        results = []
        async for doc in cursor:
            score = doc.pop("score", 0.0)
            results.append(RetrievedChunk(doc, score=score))

        logger.info(
            "Vector retrieval complete",
            query_len=len(query),
            results=len(results),
            document_id=document_id,
        )
        return results

    except Exception as e:
        # Fallback: if vector index doesn't exist yet, use text search
        logger.warning("Vector search failed, falling back to text search", error=str(e))
        return await _keyword_fallback(query, match_filter, k)


async def _keyword_fallback(
    query: str,
    match_filter: Dict[str, Any],
    top_k: int,
) -> List[RetrievedChunk]:
    """Simple keyword search fallback when vector index is unavailable."""
    col = document_chunks_col()
    words = query.split()[:5]  # use first 5 words
    regex = "|".join(words)

    pipeline = [
        {"$match": {**match_filter, "content": {"$regex": regex, "$options": "i"}}},
        {"$limit": top_k},
        {"$project": {"_id": 1, "document_id": 1, "content": 1, "metadata": 1,
                      "previous_chunk_id": 1, "next_chunk_id": 1}},
    ]

    cursor = col.aggregate(pipeline)
    results = []
    async for doc in cursor:
        results.append(RetrievedChunk(doc, score=0.5))
    return results


async def get_chunk_by_id(chunk_id: str) -> Optional[RetrievedChunk]:
    """Fetch a single chunk by its ID."""
    col = document_chunks_col()
    doc = await col.find_one({"_id": chunk_id})
    if doc:
        return RetrievedChunk(doc)
    return None


async def get_neighbor_chunks(
    chunk: RetrievedChunk,
    include_prev: bool = True,
    include_next: bool = True,
) -> List[RetrievedChunk]:
    """Fetch neighboring chunks for context expansion."""
    neighbors = []
    if include_prev and chunk.previous_chunk_id:
        prev = await get_chunk_by_id(chunk.previous_chunk_id)
        if prev:
            neighbors.insert(0, prev)
    if include_next and chunk.next_chunk_id:
        nxt = await get_chunk_by_id(chunk.next_chunk_id)
        if nxt:
            neighbors.append(nxt)
    return neighbors
