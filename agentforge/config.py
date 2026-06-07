"""Central configuration.

Everything is driven from environment variables (or a local ``.env``) so the
same image runs unchanged across dev / CI / prod. See ``.env.example``.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- LLM layer -------------------------------------------------------
    # Provider-agnostic model string understood by langchain's init_chat_model,
    # e.g. "anthropic:claude-opus-4-8", "openai:gpt-4o", "ollama:llama3.1".
    # Default to the most capable Claude model.
    chat_model: str = Field(default="anthropic:claude-opus-4-8")
    # Cheaper/faster model for auxiliary calls (planning, grading).
    fast_model: str = Field(default="anthropic:claude-haiku-4-5")
    max_tokens: int = Field(default=4096)

    # Provider API keys (only the one matching ``chat_model`` is required).
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    ollama_base_url: str = Field(default="http://localhost:11434")

    # --- Embeddings ------------------------------------------------------
    # init_embeddings-style string: "openai:text-embedding-3-small",
    # "ollama:nomic-embed-text", or "huggingface:BAAI/bge-small-en-v1.5".
    embedding_model: str = Field(default="ollama:nomic-embed-text")
    # Must match the embedding model's output dimensionality.
    embedding_dim: int = Field(default=768)

    # --- Vector store (Postgres + pgvector) ------------------------------
    database_url: str = Field(
        default="postgresql+psycopg://agentforge:agentforge@localhost:5432/agentforge"
    )
    collection_name: str = Field(default="agentforge_documents")

    # --- RAG retrieval ---------------------------------------------------
    retrieval_k: int = Field(default=4)
    # Normalized relevance floor in [0, 1] (higher = more similar). Chunks below
    # it are dropped, which is how the agent produces grounded refusals instead
    # of hallucinating. Calibrate per embedding model — the absolute number
    # shifts between models; 0.2 is a permissive default for nomic-embed-text.
    min_relevance: float = Field(default=0.2)
    chunk_size: int = Field(default=900)
    chunk_overlap: int = Field(default=150)

    # --- Guardrails ------------------------------------------------------
    redact_pii: bool = Field(default=True)
    # Tools that always require human approval before execution.
    sensitive_tools: list[str] = Field(default_factory=lambda: ["escalate_case", "file_sar"])

    # --- Observability ---------------------------------------------------
    # "langsmith" | "langfuse" | "none"
    observability_backend: str = Field(default="none")
    langchain_api_key: str | None = None
    langchain_project: str = Field(default="agentforge")
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str = Field(default="https://cloud.langfuse.com")

    # --- Auto-ingest -----------------------------------------------------
    # When true (set by docker-compose), the API ingests the corpus on startup
    # if the vector store is empty — this is what makes `docker compose up`
    # demo-able with no manual ingest step.
    auto_ingest: bool = Field(default=False)
    auto_ingest_corpus: str = Field(default="examples/banking-compliance/corpus")

    # --- API -------------------------------------------------------------
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:4200"])


@lru_cache
def get_settings() -> Settings:
    """Cached singleton — import this everywhere instead of constructing Settings()."""
    return Settings()
