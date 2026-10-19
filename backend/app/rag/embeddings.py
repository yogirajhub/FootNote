"""
EmbeddingService — Hugging Face Sentence Transformers.

Model is fully configurable via EMBEDDING_MODEL env var.
Singleton pattern to avoid reloading the model on every request.
"""
import asyncio
from typing import List, Optional, Any
from app.config.settings import settings
import structlog

logger = structlog.get_logger()

_model = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        logger.info("Loading embedding model", model=settings.embedding_model)
        _model = SentenceTransformer(settings.embedding_model)
        logger.info("Embedding model loaded")
    return _model


class EmbeddingService:
    """
    Wraps Sentence Transformers for generating text embeddings.
    Model is loaded lazily on first use.
    """
    
    def warmup(self):
        """Warmup the model by loading it into memory."""
        _get_model()
        
    async def async_warmup(self):
        """Async wrapper for model warmup."""
        await asyncio.to_thread(self.warmup)

    def embed_text(self, text: str) -> List[float]:
        """Embed a single string."""
        model = _get_model()
        vector = model.encode(text, convert_to_numpy=True)
        return vector.tolist()

    async def aembed_text(self, text: str) -> List[float]:
        """Async wrapper for single string embedding."""
        return await asyncio.to_thread(self.embed_text, text)

    def embed_texts(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        """Embed a list of strings in batches."""
        model = _get_model()
        logger.info("Embedding texts", count=len(texts), batch_size=batch_size)
        vectors = model.encode(
            texts,
            batch_size=batch_size,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return [v.tolist() for v in vectors]
        
    async def aembed_texts(self, texts: List[str], batch_size: int = 64) -> List[List[float]]:
        """Async wrapper for batch string embedding."""
        return await asyncio.to_thread(self.embed_texts, texts, batch_size)

    async def aembed_texts_with_progress(
        self,
        texts: List[str],
        batch_size: int = 64,
        on_batch_done: Optional[Any] = None,
    ) -> List[List[float]]:
        """Async batch embedding with incremental progress notifications."""
        if not texts:
            return []
        
        all_vectors: List[List[float]] = []
        total = len(texts)
        
        for i in range(0, total, batch_size):
            batch = texts[i : i + batch_size]
            batch_vectors = await asyncio.to_thread(self.embed_texts, batch, batch_size)
            all_vectors.extend(batch_vectors)
            if on_batch_done:
                res = on_batch_done(len(all_vectors), total)
                if asyncio.iscoroutine(res):
                    await res
                    
        return all_vectors

    @property
    def dimensions(self) -> int:
        return settings.embedding_dimensions


# Singleton instance
embedding_service = EmbeddingService()
