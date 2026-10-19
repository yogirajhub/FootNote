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

from app.rag.prompts import wants_detail, is_about_footnote_build
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

STRICT GROUNDING & ANTI-HALLUCINATION RULES:
1. Answer questions STRICTLY and ONLY based on the provided document context excerpts.
2. ABSOLUTELY NO HALLUCINATION: Never make up facts, numbers, dates, quotations, or citations. If something is not in the text, do not guess or extrapolate.
3. OUT-OF-SCOPE / ABSENT INFORMATION RULE: If the question cannot be answered from the provided document context or is outside the document's contents, gracefully state:
   "🙏 I couldn't find information about this in your uploaded document ('{document_title}'). Main sirf aapke uploaded document se hi answers de sakta hoon. Agar aapko iske baare mein jaanna hai, toh please usse related document upload karein!"
4. EXACT PROOF: In the Source line and in the Proof accordion, cite the EXACT location (Page number, Chapter name/number, Section). In the Proof accordion, quote the actual verbatim words from the document text. Never fabricate a page number or quote.
5. FOOTNOTE BUILD / INTERNAL QUESTIONS: If the user asks how FootNote was built, who built it, or queries like "tum kaise build hue ho", ALWAYS respond with:
   "I am not able to answer thus ask anything else.\n\nMain sirf aapke uploaded document ke content se hi answers de sakta hoon. Please ask anything related to your uploaded document!"

LANGUAGE RULE:
- Match the language style of the user. If the user writes in English, respond in English.
- If the user writes in Hinglish (Hindi + English mix), respond in Hinglish too.
- If the user writes in Hindi, respond in Hindi.
- Keep technical terms in English regardless of language.

CRITICAL INSTRUCTION: You must format your response EXACTLY as follows, using Markdown `<details>` tags for the dropdowns. Do not add any extra text outside this structure.

**Answer**
[A short and crisp direct answer to the user's question, maximum 2-3 sentences unless the user explicitly asked for "in detail"]

📖 **Source:** [ALWAYS mention the exact location: Page number, Chapter name/number, Section name — e.g. "Page 12, Chapter 3: Gravity". This proves your answer is from the document.]

<details>
<summary>Proof</summary>
[STRICT LENGTH RULE: Maximum 1-2 concise lines, strictly under 3 lines total at all costs! Simply state: "Page X ke is part ke base par: '...brief 10-15 word exact quote...'". Never exceed 3 lines.]
</details>

<details>
<summary>Simple Explanation</summary>
[A plain, easy to understand explanation of the concept — in the same language style as the user's question]
</details>

<details>
<summary>Example</summary>
[A short story, analogy, or practical example illustrating the concept]
</details>"""

_DETAIL_SYSTEM_INSTRUCTION = """
IN-DEPTH & STRUCTURED EXPLANATION INSTRUCTION (USER ASKED "IN DETAIL"):
The user has requested an in-depth, thorough, and well-structured explanation. In your **Answer** section:
1. Provide a comprehensive, rich, step-by-step deep dive into the subject.
2. Include a clean, well-formatted Markdown Table (e.g. `| Concept / Key Element | Detailed Explanation from Document | Page / Reference |`) to organize and summarize the core insights clearly so the user can easily compare and read the information.
3. Use structured subheadings or bullet points for readability.
4. Keep the 📖 **Source:** line and the <details><summary>Proof</summary>, <details><summary>Simple Explanation</summary>, and <details><summary>Example</summary> dropdowns underneath.
"""


_SYSTEM_PROMPT_FOLLOWUP = """You are FootNote, continuing a conversation about a document.
Maintain context from the conversation history. Answer based strictly on the provided document excerpts.

STRICT GROUNDING & ANTI-HALLUCINATION:
1. Answer strictly and only from the document context.
2. If asked how FootNote was built or "tum kaise build hue ho", ALWAYS respond: "I am not able to answer thus ask anything else.\n\nMain sirf aapke uploaded document ke content se hi answers de sakta hoon."

LANGUAGE RULE: Match the user's language style — English, Hinglish, or Hindi.

CRITICAL INSTRUCTION: You must format your response EXACTLY as follows, using Markdown `<details>` tags:

**Answer**
[Crisp direct answer to the user's question, maximum 2-3 sentences unless "in detail" was asked]

📖 **Source:** [Page number, Chapter name/number, Section]

<details>
<summary>Proof</summary>
[STRICT LENGTH RULE: Maximum 1-2 concise lines, strictly under 3 lines total at all costs! State: "Page X ke is part ke base par: '...brief 10-15 word exact quote...'". Never exceed 3 lines.]
</details>

<details>
<summary>Simple Explanation</summary>
[A plain, easy to understand explanation]
</details>

<details>
<summary>Example</summary>
[A short story, analogy, or practical example]
</details>"""


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

    # ── 1b. Check if user is asking how FootNote was built / who built FootNote ──
    if is_about_footnote_build(query):
        footnote_build_msg = (
            "I am not able to answer thus ask anything else.\n\n"
            "Main sirf aapke uploaded document ke content se hi answers de sakta hoon. "
            "Please ask anything related to your uploaded document!"
        )
        return PipelineResult(
            answer=footnote_build_msg,
            passages=[],
            intent=Intent.OUT_OF_SCOPE,
            rewritten_query=query,
            latency_ms=int(timer.total_ms),
            timings=timer.timings,
        )

    # ── 2. Intent detection ───────────────────────────────────────────────────
    with timer.stage("intent"):
        intent = classify_intent(query, conversation_history, document_title=document_title)
    logger.info("Intent classified", intent=intent, query=query[:80])


    if intent == Intent.OUT_OF_SCOPE:
        out_of_scope_msg = (
            "🙏 I don't have information about this topic in your uploaded document.\n\n"
            "Main sirf aapke uploaded document ke content se hi answers de sakta hoon. "
            "I can only answer questions that are related to the document you've uploaded here.\n\n"
            "**Agar aapko iske baare mein jaanna hai, toh please isse related document upload karein** "
            "aur phir mujhse poochein — I'll be happy to help! 📄\n\n"
            "For now, try asking something about **\"" + document_title + "\"** — "
            "like 'What is the main idea?' ya 'Summarize the introduction.'"
        )
        return PipelineResult(
            answer=out_of_scope_msg,
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
        no_results_msg = (
            f"Hmm, mujhe '{document_title}' mein iske baare mein kuch relevant nahi mila. 🤔\n\n"
            f"I couldn't find relevant information about this in the document. "
            f"This could mean:\n"
            f"- The document doesn't cover this specific topic\n"
            f"- Try rephrasing your question differently\n"
            f"- Ask about a specific chapter, page, or section\n\n"
            f"💡 **Tip:** You can select text from the reader and ask me about it directly!"
        )
        return PipelineResult(
            answer=no_results_msg,
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
    is_detail = wants_detail(query)
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
        is_detail=is_detail,
    )

    return (timer, safety_result, intent, rewritten_query, reranked, messages, is_detail)


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
        
    timer, safety_result, intent, rewritten_query, reranked, messages, is_detail = result

    with timer.stage("generation"):
        llm = get_llm()
        max_tokens = settings.llm_max_tokens_detail if is_detail else settings.llm_max_tokens_short
        answer = await llm.agenerate(messages, max_tokens=max_tokens, detail=is_detail, temperature=0.2)

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
        
    timer, safety_result, intent, rewritten_query, reranked, messages, is_detail = result
    
    # Build sources list from reranked passages for frontend display
    sources = []
    for chunk in reranked:
        meta = chunk.metadata
        source_info = {}
        if meta.get("page_number") or meta.get("page"):
            source_info["page"] = meta.get("page_number", meta.get("page"))
        if meta.get("chapter"):
            source_info["chapter"] = meta["chapter"]
        if meta.get("section"):
            source_info["section"] = meta["section"]
        if source_info:
            sources.append(source_info)
    
    # Deduplicate sources by page
    seen_pages = set()
    unique_sources = []
    for s in sources:
        key = (s.get("page"), s.get("chapter", ""), s.get("section", ""))
        if key not in seen_pages:
            seen_pages.add(key)
            unique_sources.append(s)
    
    yield f"data: {json.dumps({'type': 'metadata', 'intent': intent.value, 'rewritten_query': rewritten_query, 'sources': unique_sources})}\n\n"
    
    with timer.stage("generation"):
        llm = get_llm()
        max_tokens = settings.llm_max_tokens_detail if is_detail else settings.llm_max_tokens_short
        stream = llm.agenerate_stream(messages, max_tokens=max_tokens, detail=is_detail, temperature=0.2)
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
    is_detail: bool = False,
) -> List[Dict]:
    active_prompt = system_prompt
    if is_detail:
        active_prompt = active_prompt + "\n\n" + _DETAIL_SYSTEM_INSTRUCTION
    messages = [{"role": "system", "content": active_prompt}]

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

