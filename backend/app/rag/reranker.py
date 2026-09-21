"""
Reranker — pluggable reranking module.

MVP: cosine similarity reranking using the query embedding vs chunk embeddings.
Architecture allows dropping in a cross-encoder (e.g., ms-marco-MiniLM) later
by implementing a new Reranker subclass.
"""
from abc import ABC, abstractmethod
from typing import List
from app.rag.retriever import RetrievedChunk
from app.rag.embeddings import embedding_service
from app.config.settings import settings
import numpy as np
import structlog

logger = structlog.get_logger()


class BaseReranker(ABC):
    @abstractmethod
    def rerank(self, query: str, chunks: List[RetrievedChunk], top_k: int) -> List[RetrievedChunk]:
        ...


class CosineReranker(BaseReranker):
    """
    Reranks chunks by cosine similarity between query embedding and chunk embedding.
    Used as the default reranker for MVP.
    """

    def rerank(self, query: str, chunks: List[RetrievedChunk], top_k: int) -> List[RetrievedChunk]:
        if not chunks:
            return []

        query_vec = np.array(embedding_service.embed_text(query))
        chunk_texts = [c.content for c in chunks]
        chunk_vecs = np.array(embedding_service.embed_texts(chunk_texts))

        # Cosine similarity
        query_norm = np.linalg.norm(query_vec)
        chunk_norms = np.linalg.norm(chunk_vecs, axis=1)

        similarities = []
        for i, (chunk_vec, norm) in enumerate(zip(chunk_vecs, chunk_norms)):
            if query_norm > 0 and norm > 0:
                sim = float(np.dot(query_vec, chunk_vec) / (query_norm * norm))
            else:
                sim = 0.0
            similarities.append((i, sim))

        # Sort by score descending
        similarities.sort(key=lambda x: x[1], reverse=True)

        reranked = []
        for idx, score in similarities[:top_k]:
            chunk = chunks[idx]
            chunk.score = score
            reranked.append(chunk)

        logger.info("Reranking complete", input=len(chunks), output=len(reranked))
        return reranked


# Default reranker instance (swap this to use a cross-encoder)
reranker = CosineReranker()
