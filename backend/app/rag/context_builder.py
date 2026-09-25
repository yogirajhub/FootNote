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


from app.config.settings import settings

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
) -> BuiltContext:
    """
    Build the final context block for LLM generation.

    Process:
    1. Apply token budget to primary chunks (relevance order).
    2. Apply remaining budget to neighbor chunks.
    3. Sort kept chunks by document order (page number).
    4. Label chunks (C1..Cn for primary, N for neighbors).
    5. Format with source metadata.
    """
    ctx = BuiltContext()
    seen_ids = set()
    kept_primary: List[RetrievedChunk] = []
    kept_neighbors: List[RetrievedChunk] = []
    
    max_tokens = settings.context_max_tokens
    total_tokens = 0
    
    # 1. Primary chunks (apply budget in relevance order)
    for chunk in primary_chunks:
        if chunk.chunk_id not in seen_ids:
            chunk_tokens = _estimate_tokens(chunk.content)
            if total_tokens + chunk_tokens > max_tokens:
                break
            kept_primary.append(chunk)
            seen_ids.add(chunk.chunk_id)
            total_tokens += chunk_tokens

    # 2. Neighbor chunks (apply remaining budget)
    if neighbor_chunks:
        for chunk in neighbor_chunks:
            if chunk.chunk_id not in seen_ids:
                chunk_tokens = _estimate_tokens(chunk.content)
                if total_tokens + chunk_tokens > max_tokens:
                    break
                kept_neighbors.append(chunk)
                seen_ids.add(chunk.chunk_id)
                total_tokens += chunk_tokens

    # 3. Combine and sort by page number
    all_kept = kept_primary + kept_neighbors
    all_kept.sort(key=lambda c: c.metadata.get("page_number", c.metadata.get("page", 0)))
    
    # 4. Determine labels
    labels = {}
    for i, c in enumerate(kept_primary, 1):
        labels[c.chunk_id] = f"C{i}"
    for c in kept_neighbors:
        labels[c.chunk_id] = "N"

    # 5. Build context text
    context_parts: List[str] = []
    
    for chunk in all_kept:
        meta = chunk.metadata
        source_parts = []
        if meta.get("chapter"):
            source_parts.append(meta["chapter"])
        if meta.get("section"):
            source_parts.append(meta["section"])
        
        page = meta.get("page_number", meta.get("page"))
        if page:
            source_parts.append(f"Page {page}")

        source_label = " › ".join(source_parts) if source_parts else "Source"
        label = labels[chunk.chunk_id]
        context_parts.append(f"[{label}] [{source_label}]\n{chunk.content}")

        ctx.passages.append(chunk)
        ctx.source_chunks.append(chunk.chunk_id)

    ctx.context_text = "\n\n---\n\n".join(context_parts)
    ctx.token_count = total_tokens

    logger.info(
        "Context built",
        passages=len(ctx.passages),
        tokens=ctx.token_count,
        candidates=len(primary_chunks) + (len(neighbor_chunks) if neighbor_chunks else 0),
    )
    return ctx
