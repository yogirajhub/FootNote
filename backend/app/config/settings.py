from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import List
import os


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── App ──────────────────────────────────────────────────────────
    app_name: str = "FootNote"
    app_version: str = "1.0.0"
    environment: str = "development"
    log_level: str = "INFO"

    # ── MongoDB ──────────────────────────────────────────────────────
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_database: str = "footnote"

    # ── Embeddings ───────────────────────────────────────────────────
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    vector_index_name: str = "chunk_embeddings_index"
    embedding_dimensions: int = 384  # all-MiniLM-L6-v2 output size
    embedding_warmup: bool = True    # warm up model at startup (L3)

    # ── LLM ──────────────────────────────────────────────────────────
    llm_provider: str = "groq"
    llm_model: str = "openai/gpt-oss-20b"
    groq_api_key: str = ""
    llm_reasoning_effort: str = "low"    # "low"|"medium"|"high" (L7)
    llm_max_tokens_short: int = 700      # short answer cap (L7)
    llm_max_tokens_detail: int = 1600    # "in detail" cap (L7)
    llm_timeout_s: float = 20.0          # stream timeout seconds (L7)

    # ── File Upload ───────────────────────────────────────────────────
    max_upload_size: int = 52428800  # 50 MB
    upload_dir: str = "./uploads"
    allowed_extensions: List[str] = ["pdf", "docx", "txt", "md", "epub"]

    # ── RAG ───────────────────────────────────────────────────────────
    retrieval_top_k: int = 6        # chunks fetched from vector search (L8)
    rerank_top_k: int = 4           # chunks kept after rerank (L8)
    chunk_size: int = 512
    chunk_overlap: int = 64
    context_max_tokens: int = 2200  # LLM context budget (L8)
    min_relevance: float = 0.25     # relevance gate threshold (A4)

    # ── Query rewriter ────────────────────────────────────────────────
    enable_llm_rewrite: bool = False  # LLM rewrite only when True (L4)

    # ── Reranker ──────────────────────────────────────────────────────
    reranker_type: str = "passthrough"  # "passthrough"|"cosine" (L1)

    # ── Demo User (MVP) ───────────────────────────────────────────────
    demo_user_id: str = "demo_user_001"
    demo_user_name: str = "Demo User"

    # ── CORS ──────────────────────────────────────────────────────────
    allowed_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    @property
    def cors_origins(self) -> List[str]:
        return [o.strip() for o in self.allowed_origins.split(",")]

    @property
    def is_development(self) -> bool:
        return self.environment == "development"


settings = Settings()
