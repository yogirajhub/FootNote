"""
Query rewriter — uses Groq LLM to rewrite follow-up questions
into standalone queries, preserving document context.
"""
from typing import List, Optional, Dict
from app.config.settings import settings
import structlog

logger = structlog.get_logger()


class QueryRewriter:
    """
    Rewrites queries using conversation history to produce standalone questions.
    Falls back to original query if LLM is unavailable.
    """

    def rewrite(
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

        # Build a compact history string (last 4 turns)
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
            from groq import Groq
            client = Groq(api_key=settings.groq_api_key)
            response = client.chat.completions.create(
                model=settings.llm_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=150,
                temperature=0.1,
            )
            rewritten = response.choices[0].message.content.strip()
            logger.info("Query rewritten", original=query, rewritten=rewritten)
            return rewritten if rewritten else query
        except Exception as e:
            logger.warning("Query rewriting failed, using original", error=str(e))
            return query


query_rewriter = QueryRewriter()
