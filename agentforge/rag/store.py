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


# Metadata key every chunk is tagged with so retrieval can scope to one tenant.
TENANT_FIELD = "tenant_id"


def tenant_filter(tenant_id: str):
    """A backend-appropriate metadata filter selecting one tenant's chunks.

    Both backends store the chunk's LangChain metadata, but their filter
    dialects differ: pgvector takes a Mongo-style operator dict over the jsonb
    column, while Qdrant needs a typed ``Filter`` over the ``metadata`` payload
    key. Returning the right object here keeps ``retrieve`` backend-agnostic.
    """
    backend = get_settings().vector_store_backend.lower()
    if backend == "qdrant":
        from qdrant_client import models

        return models.Filter(
            must=[
                models.FieldCondition(
                    key=f"metadata.{TENANT_FIELD}",
                    match=models.MatchValue(value=tenant_id),
                )
            ]
        )
    # pgvector (langchain_postgres) operator-dict over the jsonb metadata.
    return {TENANT_FIELD: {"$eq": tenant_id}}


def collection_is_empty(tenant_id: str | None = None) -> bool:
    """True if the store holds no documents (used to guard auto-ingest).

    ``similarity_search`` returns the top-k regardless of distance, so a single
    hit means the collection is populated; an empty list means it isn't. When
    ``tenant_id`` is given, the check is scoped to that tenant's chunks.
    """
    try:
        kwargs = {"filter": tenant_filter(tenant_id)} if tenant_id is not None else {}
        return len(get_vector_store().similarity_search("ping", k=1, **kwargs)) == 0
    except Exception:
        # Collection not created yet / store unreachable — treat as empty.
        return True


def backfill_tenant(tenant_id: str) -> int:
    """Stamp untagged legacy chunks with ``tenant_id`` (metadata-only, no re-embed).

    Idempotent: only rows missing the ``tenant_id`` field are touched, so it is
    safe to run on every startup. Lets pre-multitenancy corpora keep working with
    zero re-ingest — they simply become the default tenant's knowledge base.
    Returns the number of chunks updated.
    """
    settings = get_settings()
    if settings.vector_store_backend.lower() == "qdrant":
        return _backfill_qdrant(settings, tenant_id)
    return _backfill_pgvector(settings, tenant_id)


def _backfill_pgvector(settings: Settings, tenant_id: str) -> int:
    import json

    import psycopg

    from agentforge.config import libpq_url

    # Add tenant_id only to this collection's rows that don't already have it.
    sql = """
    UPDATE langchain_pg_embedding e
    SET cmetadata = e.cmetadata || %s::jsonb
    FROM langchain_pg_collection c
    WHERE c.uuid = e.collection_id
      AND c.name = %s
      AND NOT (e.cmetadata ? 'tenant_id')
    """
    patch = json.dumps({TENANT_FIELD: tenant_id})
    with psycopg.connect(libpq_url(settings.database_url), connect_timeout=5) as conn:
        cur = conn.execute(sql, (patch, settings.collection_name))
        conn.commit()
        return cur.rowcount


def _backfill_qdrant(settings: Settings, tenant_id: str) -> int:
    from qdrant_client import QdrantClient, models

    client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
    if not client.collection_exists(settings.collection_name):
        return 0
    # Points whose metadata.tenant_id is absent → set it to the default tenant.
    untagged = models.Filter(
        must=[models.IsEmptyCondition(is_empty=models.PayloadField(key=f"metadata.{TENANT_FIELD}"))]
    )
    before = client.count(settings.collection_name, count_filter=untagged, exact=True).count
    if before:
        # ``key="metadata"`` merges into the nested metadata object rather than
        # overwriting it, so source/title survive the stamp.
        client.set_payload(
            collection_name=settings.collection_name,
            payload={TENANT_FIELD: tenant_id},
            key="metadata",
            points=untagged,
            wait=True,
        )
    return before
