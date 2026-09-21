"""
Intent classifier — detects user intent from query + conversation context.
"""
from enum import Enum
from typing import Optional, List, Dict
import re


class Intent(str, Enum):
    DOCUMENT_QUESTION = "DOCUMENT_QUESTION"
    PASSAGE_EXPLANATION = "PASSAGE_EXPLANATION"
    FOLLOW_UP = "FOLLOW_UP"
    RELATED_PASSAGES = "RELATED_PASSAGES"
    SECTION_QUERY = "SECTION_QUERY"
    CHAPTER_QUERY = "CHAPTER_QUERY"
    SUMMARY = "SUMMARY"
    COMPARISON = "COMPARISON"
    QUOTE_REQUEST = "QUOTE_REQUEST"
    NAVIGATION = "NAVIGATION"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"


_FOLLOW_UP_PATTERNS = [
    r"^(why|how|what|when|where|who) (does|did|is|was|are|were|can|could|would|will) (it|this|that|they|he|she)",
    r"^(can you )?(explain|tell me more|elaborate|expand|clarify)",
    r"^(what about|and|but|also|so)",
    r"^(give me an example|example of this|for example)",
]

_SUMMARY_PATTERNS = [
    r"\b(summarize?|summary|overview|brief|tldr|main point|key point|gist)\b",
]

_EXPLANATION_PATTERNS = [
    r"\b(explain|what does .+ mean|define|definition|in simple|layman|eli5)\b",
]

_QUOTE_PATTERNS = [
    r"\b(quote|exact words|verbatim|passage|text from|cite)\b",
]

_NAVIGATION_PATTERNS = [
    r"\b(chapter|section|page|part|go to|navigate|show me)\b",
    r"\b(table of contents|index|structure)\b",
]

_RELATED_PATTERNS = [
    r"\b(related|similar|other passages|find more|also discuss)\b",
]

_COMPARISON_PATTERNS = [
    r"\b(compare|difference|contrast|vs\.?|versus|similar to)\b",
]


def classify_intent(
    query: str,
    conversation_history: Optional[List[Dict]] = None,
) -> Intent:
    q = query.lower().strip()

    # Out of scope: greetings or off-topic
    if len(q) < 3 or q in {"hi", "hello", "hey", "thanks", "thank you", "ok", "okay"}:
        return Intent.OUT_OF_SCOPE

    # Check for follow-up patterns first (most important)
    has_history = bool(conversation_history and len(conversation_history) >= 2)
    if has_history:
        for pat in _FOLLOW_UP_PATTERNS:
            if re.search(pat, q, re.IGNORECASE):
                return Intent.FOLLOW_UP

    if any(re.search(p, q) for p in _SUMMARY_PATTERNS):
        return Intent.SUMMARY

    if any(re.search(p, q) for p in _QUOTE_PATTERNS):
        return Intent.QUOTE_REQUEST

    if any(re.search(p, q) for p in _EXPLANATION_PATTERNS):
        return Intent.PASSAGE_EXPLANATION

    if any(re.search(p, q) for p in _COMPARISON_PATTERNS):
        return Intent.COMPARISON

    if any(re.search(p, q) for p in _NAVIGATION_PATTERNS):
        return Intent.NAVIGATION

    if any(re.search(p, q) for p in _RELATED_PATTERNS):
        return Intent.RELATED_PASSAGES

    return Intent.DOCUMENT_QUESTION
