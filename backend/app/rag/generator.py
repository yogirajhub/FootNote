"""
LLM Generator — Groq-backed generation with streaming support.
Abstracted via LLMProvider base class to allow provider swaps.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Generator, AsyncGenerator
from app.config.settings import settings
import structlog

logger = structlog.get_logger()


class LLMProvider(ABC):
    @abstractmethod
    def generate(self, messages: List[Dict], max_tokens: int = 1024, temperature: float = 0.3) -> str:
        ...

    @abstractmethod
    def generate_stream(self, messages: List[Dict], max_tokens: int = 1024) -> Generator[str, None, None]:
        ...
        
    @abstractmethod
    async def agenerate(self, messages: List[Dict], max_tokens: Optional[int] = None, detail: bool = False, temperature: float = 0.3) -> str:
        ...
        
    @abstractmethod
    async def agenerate_stream(self, messages: List[Dict], max_tokens: Optional[int] = None, detail: bool = False, temperature: float = 0.3) -> AsyncGenerator[str, None]:
        ...


class GroqProvider(LLMProvider):
    def __init__(self):
        from groq import Groq, AsyncGroq
        self._client = Groq(api_key=settings.groq_api_key)
        self._aclient = AsyncGroq(api_key=settings.groq_api_key, max_retries=1, timeout=settings.llm_timeout_s)
        self._model = settings.llm_model

    def generate(self, messages: List[Dict], max_tokens: int = 1024, temperature: float = 0.3) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return response.choices[0].message.content.strip()

    def generate_stream(self, messages: List[Dict], max_tokens: int = 1024) -> Generator[str, None, None]:
        stream = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.3,
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
                
    def _get_max_tokens(self, max_tokens: Optional[int], detail: bool) -> int:
        if max_tokens is not None:
            return max_tokens
        return settings.llm_max_tokens_detail if detail else settings.llm_max_tokens_short
        
    async def agenerate(self, messages: List[Dict], max_tokens: Optional[int] = None, detail: bool = False, temperature: float = 0.3) -> str:
        tokens = self._get_max_tokens(max_tokens, detail)
        response = await self._aclient.chat.completions.create(
            model=self._model,
            messages=messages,
            max_tokens=tokens,
            temperature=temperature,
            extra_body={"reasoning_effort": settings.llm_reasoning_effort}
        )
        return response.choices[0].message.content.strip()

    async def agenerate_stream(self, messages: List[Dict], max_tokens: Optional[int] = None, detail: bool = False, temperature: float = 0.3) -> AsyncGenerator[str, None]:
        tokens = self._get_max_tokens(max_tokens, detail)
        stream = await self._aclient.chat.completions.create(
            model=self._model,
            messages=messages,
            max_tokens=tokens,
            temperature=temperature,
            stream=True,
            extra_body={"reasoning_effort": settings.llm_reasoning_effort}
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta


def get_llm_provider() -> LLMProvider:
    """Factory — returns the configured LLM provider."""
    provider = settings.llm_provider.lower()
    if provider == "groq":
        return GroqProvider()
    raise ValueError(f"Unsupported LLM provider: {provider}")


# Singleton
_llm: Optional[LLMProvider] = None


def get_llm() -> LLMProvider:
    global _llm
    if _llm is None:
        _llm = get_llm_provider()
    return _llm
