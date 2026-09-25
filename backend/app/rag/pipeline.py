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
from app.utils.timing import StageTimer
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

CRITICAL INSTRUCTION: You must format your response EXACTLY as follows, using Markdown `<details>` tags for the dropdowns. Do not add any extra text outside this structure.

**Answer**
[A short and crisp direct answer to the user's question, maximum 2-3 sentences unless the user explicitly asked for "in detail"]

<details>
<summary>Proof</summary>
[Quote a maximum of 2 lines from the text that proves your answer, along with the source e.g. "Page 4, Chapter 1"]
</details>

<details>
<summary>Simple Explanation</summary>
[A plain English, easy to understand explanation of the concept]
</details>

<details>
<summary>Example</summary>
[A short story, analogy, or practical example illustrating the concept]
</details>"""

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
    timings: Optional[Dict[str, float]] = None


async def _prepare_rag_pipeline(
    query: str,
    document_id: str,
    document_title: str,
    conversation_history: Optional[List[Dict]] = None,
    document_ids: Optional[List[str]] = None,
) -> tuple:
    timer = StageTimer()

    # ── 1. Safety check ──────────────────────────────────────────────────────
    with timer.stage("safety"):
        safety_result = safety_checker.check(query)
    
    if safety_result.is_crisis:
        return PipelineResult(
            answer=safety_result.response,
            passages=[],
            intent=Intent.OUT_OF_SCOPE,
            rewritten_query=query,
            latency_ms=int(timer.total_ms),
            timings=timer.timings,
        )

    # ── 2. Intent detection ───────────────────────────────────────────────────
    with timer.stage("intent"):
        intent = classify_intent(query, conversation_history)
    logger.info("Intent classified", intent=intent, query=query[:80])

    if intent == Intent.OUT_OF_SCOPE:
        return PipelineResult(
            answer="I'm here to help you explore the document. Please ask a question about the content!",
            passages=[],
            intent=intent,
            rewritten_query=query,
            latency_ms=int(timer.total_ms),
            timings=timer.timings,
        )

    # ── 3. Query rewriting ────────────────────────────────────────────────────
    with timer.stage("rewrite"):
        rewritten_query = await query_rewriter.arewrite(
            query=query,
            conversation_history=conversation_history,
            document_title=document_title,
        )

    # ── 4. Retrieval ──────────────────────────────────────────────────────────
    with timer.stage("retrieval"):
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
            latency_ms=int(timer.total_ms),
            timings=timer.timings,
        )

    # ── 5. Reranking ──────────────────────────────────────────────────────────
    with timer.stage("rerank"):
        reranked = reranker.rerank(rewritten_query, raw_chunks, top_k=settings.rerank_top_k)

    # ── 6. Neighbor context expansion ─────────────────────────────────────────
    with timer.stage("neighbors"):
        neighbors: List[RetrievedChunk] = []
        if reranked:
            top_chunk = reranked[0]
            neighbors = await get_neighbor_chunks(top_chunk, include_prev=True, include_next=True)

    # ── 7. Context building ───────────────────────────────────────────────────
    with timer.stage("context"):
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

    return (timer, safety_result, intent, rewritten_query, reranked, messages)


async def run_rag_pipeline(
    query: str,
    document_id: str,
    document_title: str,
    conversation_history: Optional[List[Dict]] = None,
    document_ids: Optional[List[str]] = None,
) -> PipelineResult:
    """
    Execute the full RAG pipeline for a user query (batch mode).
    """
    result = await _prepare_rag_pipeline(query, document_id, document_title, conversation_history, document_ids)
    
    # If it returned a PipelineResult directly (early exit for safety/intent out-of-scope/no chunks)
    if isinstance(result, PipelineResult):
        return result
        
    timer, safety_result, intent, rewritten_query, reranked, messages = result

    with timer.stage("generation"):
        llm = get_llm()
        answer = await llm.agenerate(messages, max_tokens=1500)

    # Add safety footer if document is mental-health related
    if safety_result.add_disclaimer:
        answer += "\n\n---\n*FootNote provides document-based information only. For personal mental health support, please consult a qualified professional.*"

    latency_ms = int(timer.total_ms)
    timer.log_summary(passages=len(reranked))

    return PipelineResult(
        answer=answer,
        passages=reranked,
        intent=intent,
        rewritten_query=rewritten_query,
        latency_ms=latency_ms,
        timings=timer.timings,
    )

import json

async def run_rag_pipeline_stream(
    query: str,
    document_id: str,
    document_title: str,
    conversation_history: Optional[List[Dict]] = None,
    document_ids: Optional[List[str]] = None,
):
    """
    Execute the RAG pipeline and yield SSE events.
    """
    result = await _prepare_rag_pipeline(query, document_id, document_title, conversation_history, document_ids)
    
    if isinstance(result, PipelineResult):
        # Yield metadata first (intent, rewritten query, etc)
        yield f"data: {json.dumps({'type': 'metadata', 'intent': result.intent.value, 'rewritten_query': result.rewritten_query})}\n\n"
        # Yield the full static answer as a delta
        yield f"data: {json.dumps({'type': 'delta', 'content': result.answer})}\n\n"
        # Yield final message
        yield f"data: {json.dumps({'type': 'done', 'processing_time_ms': result.latency_ms, 'timings': result.timings})}\n\n"
        return
        
    timer, safety_result, intent, rewritten_query, reranked, messages = result
    
    yield f"data: {json.dumps({'type': 'metadata', 'intent': intent.value, 'rewritten_query': rewritten_query})}\n\n"
    
    with timer.stage("generation"):
        llm = get_llm()
        stream = llm.agenerate_stream(messages, max_tokens=1500)
        async for chunk in stream:
            yield f"data: {json.dumps({'type': 'delta', 'content': chunk})}\n\n"

    if safety_result.add_disclaimer:
        disclaimer = {'type': 'delta', 'content': '\n\n---\n*FootNote provides document-based information only. For personal mental health support, please consult a qualified professional.*'}
        yield f"data: {json.dumps(disclaimer)}\n\n"
        
    latency_ms = int(timer.total_ms)
    timer.log_summary(passages=len(reranked))
    yield f"data: {json.dumps({'type': 'done', 'processing_time_ms': latency_ms, 'timings': timer.timings})}\n\n"


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
