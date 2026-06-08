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

    # --- Vector store ----------------------------------------------------
    # Which backend holds the embeddings: "pgvector" (default) or "qdrant".
    vector_store_backend: str = Field(default="pgvector")
    database_url: str = Field(
        default="postgresql+psycopg://agentforge:agentforge@localhost:5432/agentforge"
    )
    collection_name: str = Field(default="agentforge_documents")
    # Qdrant connection (used when vector_store_backend == "qdrant").
    qdrant_url: str = Field(default="http://localhost:6333")
    qdrant_api_key: str | None = None
    # Graph checkpointer backend: "memory" (in-process, dev/tests) or "postgres"
    # (durable — HITL state survives restarts and is shared across replicas).
    # docker-compose / k8s set this to "postgres".
    checkpoint_backend: str = Field(default="memory")

    # --- RAG retrieval ---------------------------------------------------
    retrieval_k: int = Field(default=4)
    # Normalized relevance floor in [0, 1] (higher = more similar). Chunks below
    # it are dropped, which is how the agent produces grounded refusals instead
    # of hallucinating. Calibrate per embedding model — the absolute number
    # shifts between models; 0.2 is a permissive default for nomic-embed-text.
    min_relevance: float = Field(default=0.2)
    chunk_size: int = Field(default=900)
    chunk_overlap: int = Field(default=150)

    # --- Agent -----------------------------------------------------------
    # Override the agent's system prompt to retarget it at another domain
    # (see examples/). None keeps the built-in banking-compliance default.
    system_prompt: str | None = Field(default=None)

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

    # --- Evals -----------------------------------------------------------
    # JSON report written by evals/run_evals.py --out, served at GET /evals for
    # the console's Eval view. Absent until a run produces it.
    evals_results_path: str = Field(default="evals/results.json")

    # --- API -------------------------------------------------------------
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:4200"])


@lru_cache
def get_settings() -> Settings:
    """Cached singleton — import this everywhere instead of constructing Settings()."""
    return Settings()


def libpq_url(database_url: str) -> str:
    """SQLAlchemy URL -> libpq conninfo.

    The app uses ``postgresql+psycopg://…`` for langchain/SQLAlchemy; psycopg and
    its pool want a plain ``postgresql://…``. Only the scheme is rewritten.
    """
    return database_url.replace("postgresql+psycopg://", "postgresql://", 1)
