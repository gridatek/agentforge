"""Ingestion: load a corpus from disk, chunk it, and write it to the vector store.

Usage:
    python -m agentforge.rag.ingest examples/banking-compliance/corpus
"""

from __future__ import annotations

import sys
from pathlib import Path

from langchain_core.documents import Document

from agentforge.config import get_settings
from agentforge.rag.chunking import split_documents
from agentforge.rag.store import TENANT_FIELD, get_vector_store

SUPPORTED_SUFFIXES = {".md", ".txt", ".markdown"}


def load_corpus(corpus_dir: str | Path) -> list[Document]:
    """Read every supported text file under ``corpus_dir`` into a Document."""
    root = Path(corpus_dir)
    if not root.exists():
        raise FileNotFoundError(f"Corpus directory not found: {root}")

    documents: list[Document] = []
    for path in sorted(root.rglob("*")):
        if path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8")
        documents.append(
            Document(
                page_content=text,
                metadata={"source": str(path.relative_to(root)), "title": path.stem},
            )
        )
    return documents


def ingest(corpus_dir: str | Path, tenant_id: str | None = None) -> int:
    """Load → chunk → tag with tenant → embed → store. Returns chunks written.

    Every chunk is stamped with ``tenant_id`` so retrieval can scope to one
    tenant's knowledge base. Defaults to the configured default tenant.
    """
    tenant = tenant_id or get_settings().default_tenant
    documents = load_corpus(corpus_dir)
    chunks = split_documents(documents)
    for chunk in chunks:
        chunk.metadata[TENANT_FIELD] = tenant
    if chunks:
        get_vector_store().add_documents(chunks)
    return len(chunks)


def ingest_if_empty(corpus_dir: str | Path, tenant_id: str | None = None) -> int:
    """Ingest only when the tenant's store is empty — idempotent across restarts.

    Returns the number of chunks written (0 if already populated).
    """
    from agentforge.rag.store import collection_is_empty

    tenant = tenant_id or get_settings().default_tenant
    if not collection_is_empty(tenant):
        return 0
    return ingest(corpus_dir, tenant)


def main() -> None:
    corpus_dir = sys.argv[1] if len(sys.argv) > 1 else "examples/banking-compliance/corpus"
    count = ingest(corpus_dir)
    print(f"Ingested {count} chunks from {corpus_dir}")


if __name__ == "__main__":
    main()
