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


def collection_is_empty() -> bool:
    """True if the store holds no documents (used to guard auto-ingest).

    ``similarity_search`` returns the top-k regardless of distance, so a single
    hit means the collection is populated; an empty list means it isn't.
    """
    try:
        return len(get_vector_store().similarity_search("ping", k=1)) == 0
    except Exception:
        # Table not created yet / store unreachable — treat as empty.
        return True
