"""Read-only catalog of what's ingested in the vector store.

Powers the console's Knowledge view so RAG grounding is transparent. Queries the
``langchain_postgres`` tables directly (grouping chunks by their ``source``
metadata) rather than embedding a search, so the listing is exact.
"""

from __future__ import annotations

from dataclasses import dataclass

from agentforge.config import get_settings, libpq_url

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


def list_documents() -> list[DocumentSummary]:
    """One row per ingested source document, or ``[]`` if the store is unreachable."""
    import psycopg

    settings = get_settings()
    try:
        with psycopg.connect(libpq_url(settings.database_url), connect_timeout=3) as conn:
            rows = conn.execute(_SQL, (settings.collection_name,)).fetchall()
    except Exception:
        # Store not provisioned yet / unreachable — empty catalog, not an error.
        return []

    return [
        DocumentSummary(source=row[0] or "(unknown)", title=row[1] or "", chunks=row[2])
        for row in rows
    ]
