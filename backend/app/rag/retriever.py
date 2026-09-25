"""
Retriever — MongoDB vector search + keyword fallback.

Retrieval is always document-scoped by default.
Cross-document mode can be enabled by passing multiple document_ids.
"""
from __future__ import annotations
from typing import List, Optional, Dict, Any, Tuple
import asyncio
import numpy as np
from app.db.mongodb import document_chunks_col
from app.rag.embeddings import embedding_service
from app.config.settings import settings
import structlog

logger = structlog.get_logger()

_vector_search_available = True

def set_vector_search_available(available: bool):
    global _vector_search_available
    _vector_search_available = available
    
class _VectorCache:
    def __init__(self, max_docs: int = 10):
        self.max_docs = max_docs
        self.cache: Dict[str, Tuple[np.ndarray, List[RetrievedChunk]]] = {}
        self.access_order: List[str] = []
        self._lock = asyncio.Lock()
        
    async def get_or_load(self, document_id: str) -> Tuple[np.ndarray, List[RetrievedChunk]]:
        async with self._lock:
            if document_id in self.cache:
                self.access_order.remove(document_id)
                self.access_order.append(document_id)
                return self.cache[document_id]
                
            # Need to load
            col = document_chunks_col()
            cursor = col.find({"document_id": document_id})
            chunks = []
            embeddings = []
            
            async for doc in cursor:
                emb = doc.pop("embedding", None)
                if emb:
                    embeddings.append(emb)
                    chunks.append(RetrievedChunk(doc))
                    
            if not chunks:
                return np.array([]), []
                
            matrix = np.array(embeddings, dtype=np.float32)
            # Normalize for cosine similarity
            norms = np.linalg.norm(matrix, axis=1, keepdims=True)
            matrix = np.divide(matrix, norms, out=np.zeros_like(matrix), where=norms!=0)
            
            if len(self.cache) >= self.max_docs:
                lru_doc = self.access_order.pop(0)
                del self.cache[lru_doc]
                
            self.cache[document_id] = (matrix, chunks)
            self.access_order.append(document_id)
            return matrix, chunks
            
    def invalidate(self, document_id: str):
        if document_id in self.cache:
            del self.cache[document_id]
            self.access_order.remove(document_id)

_vector_cache = _VectorCache()

def invalidate_document_cache(document_id: str):
    _vector_cache.invalidate(document_id)


class RetrievedChunk:
    def __init__(self, data: dict, score: float = 0.0):
        self.chunk_id: str = str(data.get("_id", ""))
        self.document_id: str = data.get("document_id", "")
        self.content: str = data.get("content", "")
        self.metadata: Dict[str, Any] = data.get("metadata", {})
        self.score: float = score
        self.previous_chunk_id: Optional[str] = data.get("previous_chunk_id")
        self.next_chunk_id: Optional[str] = data.get("next_chunk_id")


async def _numpy_search(query_vec: np.ndarray, document_id: str, top_k: int) -> List[RetrievedChunk]:
    matrix, chunks = await _vector_cache.get_or_load(document_id)
    if not len(chunks):
        return []
        
    query_vec = np.array(query_vec, dtype=np.float32)
    q_norm = np.linalg.norm(query_vec)
    if q_norm > 0:
        query_vec = query_vec / q_norm
        
    scores = np.dot(matrix, query_vec)
    top_indices = np.argsort(scores)[::-1][:top_k]
    
    results = []
    for idx in top_indices:
        chunk = chunks[idx]
        # Store score directly, conversion to Atlas format ((x+1)/2) happens later if needed
        chunk.score = float(scores[idx])
        results.append(chunk)
        
    return results

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
    query_embedding = await embedding_service.aembed_text(query)

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

    col = document_chunks_col()
    
    if _vector_search_available:
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
        
        try:
            cursor = col.aggregate(pipeline)
            results = []
            async for doc in cursor:
                score = doc.pop("score", 0.0)
                if score >= settings.min_relevance:
                    results.append(RetrievedChunk(doc, score=score))

            logger.info(
                "Vector retrieval complete",
                query_len=len(query),
                results=len(results),
                document_id=document_id,
            )
            return results

        except Exception as e:
            # Fallback: if vector index doesn't exist yet, try numpy search
            logger.warning("Vector search failed, falling back to numpy search", error=str(e))
    
    # Numpy fallback (works best for single doc)
    if not document_ids or len(document_ids) == 1:
        target_doc = document_ids[0] if document_ids else document_id
        results = await _numpy_search(query_embedding, target_doc, k)
        # Apply min_relevance threshold (assuming numpy scores are cosine sim 0-1)
        results = [r for r in results if r.score >= settings.min_relevance]
        if results:
            return results
            
    # Final fallback
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
    neighbor_ids = []
    if include_prev and chunk.previous_chunk_id:
        neighbor_ids.append(chunk.previous_chunk_id)
    if include_next and chunk.next_chunk_id:
        neighbor_ids.append(chunk.next_chunk_id)
        
    if not neighbor_ids:
        return []
        
    col = document_chunks_col()
    cursor = col.find({"_id": {"$in": neighbor_ids}})
    
    results = []
    async for doc in cursor:
        results.append(RetrievedChunk(doc))
        
    # Sort correctly so prev is before next
    neighbors = []
    if include_prev and chunk.previous_chunk_id:
        for r in results:
            if r.chunk_id == chunk.previous_chunk_id:
                neighbors.append(r)
                break
    if include_next and chunk.next_chunk_id:
        for r in results:
            if r.chunk_id == chunk.next_chunk_id:
                neighbors.append(r)
                break
                
    return neighbors
