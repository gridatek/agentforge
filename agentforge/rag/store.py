"""Vector store over a pluggable backend.

``VECTOR_STORE_BACKEND`` selects the implementation:

- ``pgvector`` (default) — Postgres + pgvector, self-hostable with the bundled DB.
- ``qdrant``            — a Qdrant instance (``agentforge[qdrant]`` extra).

Both expose the same LangChain ``VectorStore`` surface (``add_documents`` +
``similarity_search_with_relevance_scores``), so ingestion and retrieval are
backend-agnostic — only construction differs.
"""

from __future__ import annotations

from functools import lru_cache

from agentforge.config import Settings, get_settings
from agentforge.llm import get_embeddings


def _pgvector_store(settings: Settings):
    from langchain_postgres import PGVector

    return PGVector(
        embeddings=get_embeddings(),
        collection_name=settings.collection_name,
        connection=settings.database_url,
        use_jsonb=True,
    )


def _qdrant_store(settings: Settings):
    try:
        from langchain_qdrant import QdrantVectorStore
        from qdrant_client import QdrantClient
        from qdrant_client.models import Distance, VectorParams
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "VECTOR_STORE_BACKEND=qdrant requires the 'qdrant' extra: "
            "pip install 'agentforge[qdrant]'"
        ) from exc

    client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
    # Create the collection on first use (pgvector creates its tables implicitly;
    # Qdrant needs the collection + vector params up front). Cosine matches the
    # default pgvector distance, so the relevance threshold behaves the same.
    if not client.collection_exists(settings.collection_name):
        client.create_collection(
            collection_name=settings.collection_name,
            vectors_config=VectorParams(size=settings.embedding_dim, distance=Distance.COSINE),
        )
    return QdrantVectorStore(
        client=client,
        collection_name=settings.collection_name,
        embedding=get_embeddings(),
    )


@lru_cache
def get_vector_store():
    settings = get_settings()
    backend = settings.vector_store_backend.lower()
    if backend == "pgvector":
        return _pgvector_store(settings)
    if backend == "qdrant":
        return _qdrant_store(settings)
    raise ValueError(
        f"Unknown VECTOR_STORE_BACKEND: {settings.vector_store_backend!r} "
        "(use 'pgvector' or 'qdrant')"
    )


def collection_is_empty() -> bool:
    """True if the store holds no documents (used to guard auto-ingest).

    ``similarity_search`` returns the top-k regardless of distance, so a single
    hit means the collection is populated; an empty list means it isn't.
    """
    try:
        return len(get_vector_store().similarity_search("ping", k=1)) == 0
    except Exception:
        # Collection not created yet / store unreachable — treat as empty.
        return True
