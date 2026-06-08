"""Read-only catalog of what's ingested in the vector store.

Powers the console's Knowledge view so RAG grounding is transparent. Each backend
needs its own enumeration: pgvector groups rows in SQL; Qdrant scrolls points and
aggregates by source metadata.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from agentforge.config import Settings, get_settings, libpq_url

# Group the collection's chunks by source document. Joins the embedding rows to
# their collection by name so we only count this app's collection.
_SQL = """
SELECT
    e.cmetadata ->> 'source'  AS source,
    max(e.cmetadata ->> 'title') AS title,
    count(*)                  AS chunks
FROM langchain_pg_embedding e
JOIN langchain_pg_collection c ON c.uuid = e.collection_id
WHERE c.name = %s
GROUP BY e.cmetadata ->> 'source'
ORDER BY source
"""


@dataclass
class DocumentSummary:
    source: str
    title: str
    chunks: int


def _from_pgvector(settings: Settings) -> list[DocumentSummary]:
    import psycopg

    with psycopg.connect(libpq_url(settings.database_url), connect_timeout=3) as conn:
        rows = conn.execute(_SQL, (settings.collection_name,)).fetchall()
    return [
        DocumentSummary(source=row[0] or "(unknown)", title=row[1] or "", chunks=row[2])
        for row in rows
    ]


def _from_qdrant(settings: Settings) -> list[DocumentSummary]:
    from qdrant_client import QdrantClient

    client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)
    titles: dict[str, str] = {}
    chunks: dict[str, int] = defaultdict(int)

    offset = None
    while True:
        points, offset = client.scroll(
            settings.collection_name, with_payload=True, limit=256, offset=offset
        )
        for point in points:
            meta = (point.payload or {}).get("metadata", {})
            source = meta.get("source") or "(unknown)"
            chunks[source] += 1
            titles.setdefault(source, meta.get("title", ""))
        if offset is None:
            break

    return [
        DocumentSummary(source=source, title=titles.get(source, ""), chunks=count)
        for source, count in sorted(chunks.items())
    ]


def list_documents() -> list[DocumentSummary]:
    """One row per ingested source document, or ``[]`` if the store is unreachable."""
    settings = get_settings()
    try:
        if settings.vector_store_backend.lower() == "qdrant":
            return _from_qdrant(settings)
        return _from_pgvector(settings)
    except Exception:
        # Store not provisioned yet / unreachable / extra missing — empty catalog.
        return []
