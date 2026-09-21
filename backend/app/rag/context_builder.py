"""
Context builder — assembles high-quality, deduplicated context
from retrieved + neighbor chunks for LLM consumption.
"""
from typing import List, Tuple, Optional
from app.rag.retriever import RetrievedChunk
import structlog

logger = structlog.get_logger()

MAX_CONTEXT_TOKENS = 3000  # conservative limit for Groq models
_APPROX_CHARS_PER_TOKEN = 4


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // _APPROX_CHARS_PER_TOKEN)


class BuiltContext:
    def __init__(self):
        self.passages: List[RetrievedChunk] = []
        self.context_text: str = ""
        self.token_count: int = 0
        self.source_chunks: List[str] = []  # chunk_ids used


def build_context(
    primary_chunks: List[RetrievedChunk],
    neighbor_chunks: Optional[List[RetrievedChunk]] = None,
    max_tokens: int = MAX_CONTEXT_TOKENS,
) -> BuiltContext:
    """
    Build the final context block for LLM generation.

    Process:
    1. Start with top primary chunks (highest relevance score).
    2. Add neighbor chunks for context expansion.
    3. Deduplicate by chunk_id.
    4. Sort by document order (page number).
    5. Enforce token limit.
    6. Format with source metadata.
    """
    ctx = BuiltContext()
    seen_ids = set()
    candidates: List[RetrievedChunk] = []

    # Primary chunks first (already reranked)
    for chunk in primary_chunks:
        if chunk.chunk_id not in seen_ids:
            candidates.append(chunk)
            seen_ids.add(chunk.chunk_id)

    # Neighbor chunks for context expansion
    if neighbor_chunks:
        for chunk in neighbor_chunks:
            if chunk.chunk_id not in seen_ids:
                candidates.append(chunk)
                seen_ids.add(chunk.chunk_id)

    # Sort by page number to preserve reading order
    candidates.sort(key=lambda c: c.metadata.get("page", 0))

    # Build context text up to token limit
    context_parts: List[str] = []
    total_tokens = 0

    for chunk in candidates:
        chunk_tokens = _estimate_tokens(chunk.content)
        if total_tokens + chunk_tokens > max_tokens:
            break

        # Format with source metadata
        meta = chunk.metadata
        source_parts = []
        if meta.get("chapter"):
            source_parts.append(meta["chapter"])
        if meta.get("section"):
            source_parts.append(meta["section"])
        if meta.get("page"):
            source_parts.append(f"Page {meta['page']}")

        source_label = " › ".join(source_parts) if source_parts else "Source"
        context_parts.append(f"[{source_label}]\n{chunk.content}")

        ctx.passages.append(chunk)
        ctx.source_chunks.append(chunk.chunk_id)
        total_tokens += chunk_tokens

    ctx.context_text = "\n\n---\n\n".join(context_parts)
    ctx.token_count = total_tokens

    logger.info(
        "Context built",
        passages=len(ctx.passages),
        tokens=ctx.token_count,
        candidates=len(candidates),
    )
    return ctx
