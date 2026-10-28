"""
EmbeddingService — Hugging Face Sentence Transformers.

Model is fully configurable via EMBEDDING_MODEL env var.
Singleton pattern to avoid reloading the model on every request.
"""
import asyncio
import os
from typing import List, Optional, Any, Callable
from concurrent.futures import ThreadPoolExecutor
from app.config.settings import settings
import structlog

logger = structlog.get_logger()

_model = None


def _get_model():
    global _model
    if _model is None:
        import torch
        from sentence_transformers import SentenceTransformer
        
        # Optimize CPU threads for PyTorch to maximize throughput
        num_threads = min(8, max(2, os.cpu_count() or 4))
        try:
            torch.set_num_threads(num_threads)
        except Exception:
            pass

        logger.info("Loading embedding model", model=settings.embedding_model, threads=num_threads)
        _model = SentenceTransformer(settings.embedding_model)
        logger.info("Embedding model loaded")
    return _model


class EmbeddingService:
    """
    Wraps Sentence Transformers for generating text embeddings.
    Model is loaded lazily on first use.
    """
    
    def warmup(self):
        """Warmup the model by loading it into memory and running a dummy inference pass."""
        model = _get_model()
        import torch
        with torch.inference_mode():
            model.encode(["warmup"], show_progress_bar=False)
        logger.info("Embedding model warm-up complete")
        
    async def async_warmup(self):
        """Async wrapper for model warmup."""
        await asyncio.to_thread(self.warmup)

    def embed_text(self, text: str) -> List[float]:
        """Embed a single string."""
        import torch
        model = _get_model()
        with torch.inference_mode():
            vector = model.encode(
                text,
                convert_to_numpy=True,
                show_progress_bar=False,
                normalize_embeddings=True,
            )
        return vector.tolist()

    async def aembed_text(self, text: str) -> List[float]:
        """Async wrapper for single string embedding."""
        return await asyncio.to_thread(self.embed_text, text)

    def embed_texts(self, texts: List[str], batch_size: int = 64) -> List[List[float]]:
        """Embed a list of strings in batches using inference_mode and C-level list conversion."""
        if not texts:
            return []
        import torch
        model = _get_model()
        with torch.inference_mode():
            vectors = model.encode(
                texts,
                batch_size=batch_size,
                convert_to_numpy=True,
                show_progress_bar=False,
                normalize_embeddings=True,
            )
        return vectors.tolist()
        
    async def aembed_texts(self, texts: List[str], batch_size: int = 64) -> List[List[float]]:
        """Async wrapper for batch string embedding."""
        return await asyncio.to_thread(self.embed_texts, texts, batch_size)

    def embed_texts_parallel(self, texts: List[str], batch_size: int = 64, max_workers: int = 2) -> List[List[float]]:
        """
        Embed texts across parallel worker threads.
        Splits batches across workers to maximize multi-core CPU throughput.
        """
        if not texts:
            return []
        if len(texts) <= batch_size or max_workers <= 1:
            return self.embed_texts(texts, batch_size=batch_size)

        batches = [texts[i : i + batch_size] for i in range(0, len(texts), batch_size)]
        
        def _encode_batch(b: List[str]) -> List[List[float]]:
            return self.embed_texts(b, batch_size=batch_size)

        all_vectors = []
        workers = min(max_workers, len(batches))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            for batch_result in executor.map(_encode_batch, batches):
                all_vectors.extend(batch_result)
        return all_vectors

    async def aembed_texts_parallel(
        self,
        texts: List[str],
        batch_size: int = 64,
        max_workers: int = 2,
    ) -> List[List[float]]:
        """Async wrapper for parallel worker embedding."""
        return await asyncio.to_thread(self.embed_texts_parallel, texts, batch_size, max_workers)

    async def aembed_texts_pipelined(
        self,
        texts: List[str],
        batch_size: int = 128,
        on_batch_ready: Optional[Callable[[int, int, List[List[float]]], Any]] = None,
    ) -> List[List[float]]:
        """
        Async batch embedding that emits each batch as soon as computed.
        Enables pipelining (e.g. storing to database while the next batch is being encoded).
        on_batch_ready(start_idx, end_idx, batch_vectors)
        """
        if not texts:
            return []

        all_vectors: List[List[float]] = []
        total = len(texts)

        for i in range(0, total, batch_size):
            batch = texts[i : i + batch_size]
            batch_vectors = await asyncio.to_thread(self.embed_texts, batch, batch_size)
            all_vectors.extend(batch_vectors)

            if on_batch_ready:
                try:
                    res = on_batch_ready(i, i + len(batch), batch_vectors)
                    if asyncio.iscoroutine(res):
                        await res
                except Exception as e:
                    logger.warning("Error in on_batch_ready callback", error=str(e))

        return all_vectors

    async def aembed_texts_with_progress(
        self,
        texts: List[str],
        batch_size: int = 128,
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
