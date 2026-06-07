"""Vector store over Postgres + pgvector.

Self-hostable by default. A ``Qdrant`` adapter is a planned drop-in (it would
implement the same tiny surface: ``add_documents`` + ``similarity_search_with_score``).
"""

from __future__ import annotations

from functools import lru_cache

from langchain_postgres import PGVector

from agentforge.config import get_settings
from agentforge.llm import get_embeddings


@lru_cache
def get_vector_store() -> PGVector:
    settings = get_settings()
    return PGVector(
        embeddings=get_embeddings(),
        collection_name=settings.collection_name,
        connection=settings.database_url,
        use_jsonb=True,
    )
