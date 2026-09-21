"""
EmbeddingService — Hugging Face Sentence Transformers.

Model is fully configurable via EMBEDDING_MODEL env var.
Singleton pattern to avoid reloading the model on every request.
"""
from typing import List
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

    def embed_text(self, text: str) -> List[float]:
        """Embed a single string."""
        model = _get_model()
        vector = model.encode(text, convert_to_numpy=True)
        return vector.tolist()

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

    @property
    def dimensions(self) -> int:
        return settings.embedding_dimensions


# Singleton instance
embedding_service = EmbeddingService()
