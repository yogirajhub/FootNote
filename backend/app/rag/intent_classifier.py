"""
Intent classifier — detects user intent from query + conversation context.

Enhanced with robust out-of-scope detection:
- Greetings and trivial messages
- Off-topic queries (politics, sports, entertainment, cooking, etc.)
- General knowledge questions not tied to the uploaded document
"""
from enum import Enum
from typing import Optional, List, Dict
import re
from app.rag.prompts import is_about_footnote_build



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
    # Hinglish follow-up patterns
    r"^(iske baare|uske baare|iska matlab|ye kya|aur batao|thoda aur|samjhao|explain karo)",
]

_SUMMARY_PATTERNS = [
    r"\b(summarize?|summary|overview|brief|tldr|main point|key point|gist)\b",
    r"\b(saar|saransh|chhota karke|short me batao)\b",
]

_EXPLANATION_PATTERNS = [
    r"\b(explain|what does .+ mean|define|definition|in simple|layman|eli5)\b",
    r"\b(samjhao|matlab kya|kya matlab|simple me|aasan bhasha)\b",
]

_QUOTE_PATTERNS = [
    r"\b(quote|exact words|verbatim|passage|text from|cite)\b",
    r"\b(exact line|likha hai|kya likha)\b",
]

_NAVIGATION_PATTERNS = [
    r"\b(chapter|section|page|part|go to|navigate|show me)\b",
    r"\b(table of contents|index|structure)\b",
    r"\b(konsa page|kis page|chapter number)\b",
]

_RELATED_PATTERNS = [
    r"\b(related|similar|other passages|find more|also discuss)\b",
    r"\b(aur kuch|isse milta|related hai)\b",
]

_COMPARISON_PATTERNS = [
    r"\b(compare|difference|contrast|vs\.?|versus|similar to)\b",
    r"\b(fark kya|antar|tulna)\b",
]

# ── Out-of-scope detection patterns ──────────────────────────────────────────

_GREETING_EXACT = {
    "hi", "hello", "hey", "thanks", "thank you", "ok", "okay", "bye", "goodbye",
    "good morning", "good evening", "good night", "sup", "yo", "hola",
    "namaste", "namaskar", "kaise ho", "kya hal", "theek", "accha",
    "hmm", "hm", "ohh", "oh", "acha", "sahi", "haan", "ha", "nahi",
    "ji", "ji haan",
}

# Topics that are clearly off-topic for a document QA system
_OFF_TOPIC_PATTERNS = [
    # Politics
    r"\b(politics|politician|election|vote|voting|democracy|republic|parliament|congress|senate|modi|trump|biden|obama|president|prime minister|BJP|AAP|Congress party|political party|lok sabha|rajya sabha|vidhansabha)\b",
    r"\b(rajniti|chunav|sarkar|neta|mantri|pradhan mantri)\b",
    # Sports
    r"\b(cricket|football|soccer|basketball|tennis|IPL|world cup|match score|who won the|olympic|fifa|super bowl|hockey|baseball)\b",
    r"\b(khel|cricket ka|match kaisa|khelna)\b",
    # Entertainment / gossip
    r"\b(movie|film|actor|actress|bollywood|hollywood|song|singer|music|celebrity|gossip|drama|serial|tv show|web series|netflix|anime)\b",
    r"\b(gaana|gana|film kaisi|hero|heroine)\b",
    # Recipes / cooking
    r"\b(recipe|how to cook|ingredients|dish|cuisine|biryani recipe|cake recipe|pasta recipe)\b",
    r"\b(khana banana|recipe batao|kaise banaye)\b",
    # Weather
    r"\b(weather today|temperature|forecast|barish|mausam|garmi|sardi)\b",
    # Personal / chat
    r"\b(your name|who are you|are you human|are you real|what are you|tumhara naam|tum kaun|kya tum robot)\b",
    r"\b(joke sunao|joke batao|mazak|funny|tell me a joke)\b",
    # General knowledge not related to a specific document
    r"\b(capital of|population of|who invented|when was .+ born|who is the president of)\b",
    r"\b(duniya me|world me|sabse bada|sabse chhota)\b",
    # Social media / tech gossip
    r"\b(instagram|facebook|twitter|tiktok|snapchat|whatsapp|social media)\b",
    # Shopping / prices
    r"\b(price of|how much|khareedna|buy|amazon|flipkart|kitne ka)\b",
]

# Patterns that indicate user IS asking about their document
_DOCUMENT_ANCHOR_PATTERNS = [
    r"\b(book|document|paper|chapter|section|page|author|paragraph|text|article|report|this|isme|isme|yahan|document me|book me|paper me|likha|mention|written|discuss|described)\b",
    r"\b(according to|as per|the text says|as mentioned|yaha likha|isme bataya)\b",
]


def _is_off_topic(query: str, document_title: Optional[str] = None) -> bool:
    """
    Determine if a query is off-topic for a document QA system.
    Returns True if the query is clearly about something unrelated to any document.
    """
    q = query.lower().strip()

    # If query explicitly references the document, it's on-topic
    for pat in _DOCUMENT_ANCHOR_PATTERNS:
        if re.search(pat, q, re.IGNORECASE):
            return False

    # If document title itself relates to the query or category, it is on-topic!
    if document_title:
        title_lower = document_title.lower()
        title_words = set(re.findall(r"\b\w{3,}\b", title_lower))
        query_words = set(re.findall(r"\b\w{3,}\b", q))
        # Word overlap or substring match
        if any(qw in tw or tw in qw for qw in query_words for tw in title_words if len(qw) >= 4 and len(tw) >= 4):
            return False

        # If document title itself matches the same off-topic category as query, it is ON-TOPIC for this document!
        for pat in _OFF_TOPIC_PATTERNS:
            if re.search(pat, title_lower, re.IGNORECASE) and re.search(pat, q, re.IGNORECASE):
                return False

    # Check off-topic patterns
    for pat in _OFF_TOPIC_PATTERNS:
        if re.search(pat, q, re.IGNORECASE):
            return True

    return False


def classify_intent(
    query: str,
    conversation_history: Optional[List[Dict]] = None,
    document_title: Optional[str] = None,
) -> Intent:
    q = query.lower().strip()

    # Out of scope: greetings, off-topic, or questions about how FootNote was built
    if len(q) < 3 or q in _GREETING_EXACT or is_about_footnote_build(q):
        return Intent.OUT_OF_SCOPE

    # Check for clearly off-topic queries
    if _is_off_topic(q, document_title=document_title):
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
