"""
Safety checker — detects crisis queries and adds mental health disclaimers.
"""
from dataclasses import dataclass
from typing import Optional
import re


_CRISIS_KEYWORDS = [
    r"\b(suicide|suicidal|kill myself|end my life|want to die|self.harm|self harm|cutting|overdose|no reason to live)\b",
    r"\b(crisis|emergency|in danger|hurt myself|hurt someone)\b",
]

_MENTAL_HEALTH_KEYWORDS = [
    r"\b(ptsd|trauma|anxiety|depression|therapy|therapist|mental health|abuse|trauma|flashback|dissociation|panic)\b",
]

_CRISIS_RESPONSE = """I'm concerned about what you've shared. 

If you're in crisis or having thoughts of harming yourself, please reach out for support right away:

🆘 **Crisis Resources:**
- **International Association for Suicide Prevention**: https://www.iasp.info/resources/Crisis_Centres/
- **Crisis Text Line** (US): Text HOME to 741741
- **Samaritans** (UK): 116 123
- **iCall** (India): 9152987821

You don't have to face this alone. Please contact a mental health professional or emergency services if you're in immediate danger.

FootNote is a document exploration tool and cannot provide crisis support."""


@dataclass
class SafetyResult:
    is_crisis: bool
    add_disclaimer: bool
    response: Optional[str] = None


class SafetyChecker:
    def check(self, query: str) -> SafetyResult:
        q = query.lower()

        # Check for crisis
        for pattern in _CRISIS_KEYWORDS:
            if re.search(pattern, q):
                return SafetyResult(
                    is_crisis=True,
                    add_disclaimer=True,
                    response=_CRISIS_RESPONSE,
                )

        # Check for mental health context (add disclaimer to response)
        for pattern in _MENTAL_HEALTH_KEYWORDS:
            if re.search(pattern, q):
                return SafetyResult(is_crisis=False, add_disclaimer=True)

        return SafetyResult(is_crisis=False, add_disclaimer=False)


safety_checker = SafetyChecker()
