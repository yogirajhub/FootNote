"""
RAG Pipeline — orchestrates all RAG stages.

Pipeline stages:
1. Safety check
2. Intent detection
3. Query rewriting
4. Retrieval (document-scoped)
5. Reranking
6. Context building (with neighbor expansion)
7. LLM generation
8. Response formatting
"""
import time
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

from app.rag.intent_classifier import classify_intent, Intent
from app.rag.query_rewriter import query_rewriter
from app.rag.retriever import retrieve, get_neighbor_chunks, RetrievedChunk
from app.rag.reranker import reranker
from app.rag.context_builder import build_context
from app.rag.generator import get_llm
from app.safety.safety_checker import safety_checker
from app.config.settings import settings
import structlog

logger = structlog.get_logger()

_SYSTEM_PROMPT = """You are FootNote, an intelligent reading companion that helps users understand documents deeply.

Your role:
- Answer questions STRICTLY based on the provided document context
- Be clear, thoughtful, and educational
- Use simple, accessible language in explanations
- Always cite the source location (chapter, section, page)
- If the context doesn't contain the answer, say: "I couldn't find enough information about this in the current document."
- NEVER fabricate information or citations
- NEVER present yourself as a therapist or medical professional
- If the document is about psychological/mental health topics, always remind users to consult professionals

Format your response as:
📖 **Relevant Passage**
[Quote the most relevant passage from context]

📍 **Source**
[Chapter/Section/Page info]

🧠 **Simple Explanation**
[Plain English explanation of the passage]

💡 **Key Idea**
[One-sentence takeaway]

If there are related passages worth exploring, briefly mention them."""

_SYSTEM_PROMPT_FOLLOWUP = """You are FootNote, continuing a conversation about a document. 
Maintain context from the conversation history. Answer based on the provided document excerpts.
Be concise and conversational for follow-up questions while remaining grounded in the document."""


@dataclass
class PipelineResult:
    answer: str
    passages: List[RetrievedChunk]
    intent: Intent
    rewritten_query: str
    latency_ms: int
    token_count: int = 0


async def run_rag_pipeline(
    query: str,
    document_id: str,
    document_title: str,
    conversation_history: Optional[List[Dict]] = None,
    document_ids: Optional[List[str]] = None,
) -> PipelineResult:
    """
    Execute the full RAG pipeline for a user query.
    Always document-scoped unless document_ids (cross-doc mode) is provided.
    """
    start_time = time.time()

    # ── 1. Safety check ──────────────────────────────────────────────────────
    safety_result = safety_checker.check(query)
    if safety_result.is_crisis:
        return PipelineResult(
            answer=safety_result.response,
            passages=[],
            intent=Intent.OUT_OF_SCOPE,
            rewritten_query=query,
            latency_ms=int((time.time() - start_time) * 1000),
        )

    # ── 2. Intent detection ───────────────────────────────────────────────────
    intent = classify_intent(query, conversation_history)
    logger.info("Intent classified", intent=intent, query=query[:80])

    if intent == Intent.OUT_OF_SCOPE:
        return PipelineResult(
            answer="I'm here to help you explore the document. Please ask a question about the content!",
            passages=[],
            intent=intent,
            rewritten_query=query,
            latency_ms=int((time.time() - start_time) * 1000),
        )

    # ── 3. Query rewriting ────────────────────────────────────────────────────
    rewritten_query = query_rewriter.rewrite(
        query=query,
        conversation_history=conversation_history,
        document_title=document_title,
    )

    # ── 4. Retrieval ──────────────────────────────────────────────────────────
    raw_chunks = await retrieve(
        query=rewritten_query,
        document_id=document_id,
        top_k=settings.retrieval_top_k,
        document_ids=document_ids,
    )

    if not raw_chunks:
        return PipelineResult(
            answer=f"I couldn't find relevant information about this in the document '{document_title}'. Try rephrasing your question or ask about a specific chapter or topic.",
            passages=[],
            intent=intent,
            rewritten_query=rewritten_query,
            latency_ms=int((time.time() - start_time) * 1000),
        )

    # ── 5. Reranking ──────────────────────────────────────────────────────────
    reranked = reranker.rerank(rewritten_query, raw_chunks, top_k=settings.rerank_top_k)

    # ── 6. Neighbor context expansion ─────────────────────────────────────────
    neighbors: List[RetrievedChunk] = []
    if reranked:
        top_chunk = reranked[0]
        neighbors = await get_neighbor_chunks(top_chunk, include_prev=True, include_next=True)

    # ── 7. Context building ───────────────────────────────────────────────────
    context = build_context(reranked, neighbor_chunks=neighbors)

    # ── 8. LLM generation ─────────────────────────────────────────────────────
    is_followup = intent in {Intent.FOLLOW_UP, Intent.PASSAGE_EXPLANATION}
    system_prompt = _SYSTEM_PROMPT_FOLLOWUP if is_followup else _SYSTEM_PROMPT

    messages = _build_messages(
        system_prompt=system_prompt,
        context_text=context.context_text,
        query=query,
        rewritten_query=rewritten_query,
        conversation_history=conversation_history,
        document_title=document_title,
        intent=intent,
    )

    llm = get_llm()
    answer = llm.generate(messages, max_tokens=1500)

    # Add safety footer if document is mental-health related
    if safety_result.add_disclaimer:
        answer += "\n\n---\n*FootNote provides document-based information only. For personal mental health support, please consult a qualified professional.*"

    latency_ms = int((time.time() - start_time) * 1000)
    logger.info("Pipeline complete", latency_ms=latency_ms, passages=len(reranked))

    return PipelineResult(
        answer=answer,
        passages=reranked,
        intent=intent,
        rewritten_query=rewritten_query,
        latency_ms=latency_ms,
    )


def _build_messages(
    system_prompt: str,
    context_text: str,
    query: str,
    rewritten_query: str,
    conversation_history: Optional[List[Dict]],
    document_title: str,
    intent: Intent,
) -> List[Dict]:
    messages = [{"role": "system", "content": system_prompt}]

    # Add recent conversation history (last 6 turns)
    if conversation_history:
        for msg in conversation_history[-6:]:
            messages.append({
                "role": msg["role"],
                "content": msg["content"][:500],  # truncate long history
            })

    # User message with context
    user_content = f"""Document: "{document_title}"

Relevant context from the document:
---
{context_text}
---

Question: {query}"""

    if rewritten_query != query:
        user_content += f"\n(Interpreted as: {rewritten_query})"

    messages.append({"role": "user", "content": user_content})
    return messages
