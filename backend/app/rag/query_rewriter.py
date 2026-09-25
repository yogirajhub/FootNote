"""
Query rewriter — uses Groq LLM to rewrite follow-up questions
into standalone queries, preserving document context.
"""
import re
from typing import List, Optional, Dict
from app.config.settings import settings
from app.rag.generator import get_llm, GroqProvider
import structlog
import asyncio

logger = structlog.get_logger()

_ANAPHORIC_PRONOUNS = {
    "it", "that", "this", "he", "she", "they", "them", 
    "these", "those", "his", "her", "their", "the above",
    "iska", "uska", "woh", "ye", "yeh", "inme", "unme"
}

class QueryRewriter:
    """
    Rewrites queries using conversation history to produce standalone questions.
    Uses heuristics by default for low latency, falls back to LLM if enabled.
    """

    def _is_anaphoric(self, query: str) -> bool:
        words = query.lower().split()
        if len(words) < 8:
            return True
        for word in words:
            if word in _ANAPHORIC_PRONOUNS:
                return True
        return False

    async def arewrite(
        self,
        query: str,
        conversation_history: Optional[List[Dict]] = None,
        document_title: Optional[str] = None,
    ) -> str:
        """
        Rewrite a query to be standalone given conversation history.
        Returns the original query if history is empty or rewriting fails.
        """
        if not conversation_history or len(conversation_history) < 2:
            return query
            
        if not self._is_anaphoric(query):
            return query

        # Heuristic fallback: prepend last user question
        last_user_msg = next((m["content"] for m in reversed(conversation_history) if m["role"] == "user"), None)
        heuristic_rewrite = f"{last_user_msg} - {query}" if last_user_msg else query

        if not settings.enable_llm_rewrite:
            return heuristic_rewrite

        # LLM Rewrite path
        recent = conversation_history[-4:]
        history_text = "\n".join(
            f"{m['role'].upper()}: {m['content'][:200]}" for m in recent
        )

        doc_context = f" in the document '{document_title}'" if document_title else ""

        prompt = f"""Given the following conversation history{doc_context}, rewrite the last user question as a complete standalone question that can be understood without the conversation history.

Conversation history:
{history_text}

Last question: {query}

Rewritten standalone question (output ONLY the question, nothing else):"""

        try:
            llm = get_llm()
            if isinstance(llm, GroqProvider):
                # 1.5s timeout via asyncio.wait_for, since AsyncGroq client has a 20s timeout by default
                async def _call_llm():
                    return await llm.agenerate(
                        messages=[{"role": "user", "content": prompt}],
                        max_tokens=150,
                        temperature=0.1
                    )
                rewritten = await asyncio.wait_for(_call_llm(), timeout=1.5)
            else:
                rewritten = await llm.agenerate(
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=150,
                    temperature=0.1
                )
            
            if rewritten:
                logger.info("Query rewritten via LLM", original=query, rewritten=rewritten)
                return rewritten
            return heuristic_rewrite
        except Exception as e:
            logger.warning("Query rewriting failed or timed out, using heuristic", error=str(e))
            return heuristic_rewrite


query_rewriter = QueryRewriter()
