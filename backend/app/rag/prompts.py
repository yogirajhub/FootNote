"""
RAG Prompts and intent helpers.
Handles detail detection, system prompts, and formatting guidance.
"""
import re

_DETAIL_PATTERNS = [
    # English
    r"\b(in detail|detailed|elaborate|expand|more detail|tell me more|step by step|thoroughly|comprehensive|deep dive|explain (this |that )?in more detail)\b",
    # Hinglish
    r"\b(aur samjhao|detail me|details me|vistaar me|bistar se|poora samjhao|thoda aur detail|ache se samjhao|achhe se samjhao|aur batao detail me)\b",
    # Hindi (Devanagari)
    r"(विस्तार से|विस्तारपूर्वक|गहराई से|पूरा समझाइए|और समझाइए|विस्तृत|डिटेल में)",
]

_FOOTNOTE_BUILD_PATTERNS = [
    r"\b(tum|aap|tu) kaise build hue( ho)?\b",
    r"\b(tum|aap|tu) kaise (bane|bana)( ho)?\b",
    r"\b(tumhe|aapko) kisne banaya( hai)?\b",
    r"\bkisne banaya( hai)?\b",
    r"\bkaise banaya gaya\b",
    r"\bkaise build hue\b",
    r"\b(who built (you|footnote)|who created (you|footnote)|who made (you|footnote)|who developed (you|footnote))\b",
    r"\b(how (are|were) you built|how was footnote built|how (are|were) you made|how (are|were) you created|how (are|were) you developed|how is footnote built)\b",
    r"\b(footnote kaise (build hua|bana))\b",
    r"\b(tumhara|aapka) tech stack\b",
    r"\b(tumhari|aapki) architecture\b",
]

def wants_detail(query: str) -> bool:
    """
    Detect whether the user is asking for an in-depth/detailed explanation.
    Supports English, Hinglish, and Hindi (Devanagari).
    """
    if not query:
        return False
    q = query.strip().lower()
    for pattern in _DETAIL_PATTERNS:
        if re.search(pattern, q, re.IGNORECASE):
            return True
        # Also check raw string for non-ascii (like Hindi script)
        if re.search(pattern, query):
            return True
    return False

def is_about_footnote_build(query: str) -> bool:
    """
    Detect whether the user is asking about how FootNote was built or created.
    """
    if not query:
        return False
    q = query.strip().lower()
    for pattern in _FOOTNOTE_BUILD_PATTERNS:
        if re.search(pattern, q, re.IGNORECASE):
            return True
    return False

