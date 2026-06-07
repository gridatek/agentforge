"""Ingestion: load a corpus from disk, chunk it, and write it to the vector store.

Usage:
    python -m agentforge.rag.ingest examples/banking-compliance/corpus
"""

from __future__ import annotations

import sys
from pathlib import Path

from langchain_core.documents import Document

from agentforge.rag.chunking import split_documents
from agentforge.rag.store import get_vector_store

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


def ingest(corpus_dir: str | Path) -> int:
    """Load → chunk → embed → store. Returns the number of chunks written."""
    documents = load_corpus(corpus_dir)
    chunks = split_documents(documents)
    if chunks:
        get_vector_store().add_documents(chunks)
    return len(chunks)


def ingest_if_empty(corpus_dir: str | Path) -> int:
    """Ingest only when the store is empty — idempotent across restarts.

    Returns the number of chunks written (0 if already populated).
    """
    from agentforge.rag.store import collection_is_empty

    if not collection_is_empty():
        return 0
    return ingest(corpus_dir)


def main() -> None:
    corpus_dir = sys.argv[1] if len(sys.argv) > 1 else "examples/banking-compliance/corpus"
    count = ingest(corpus_dir)
    print(f"Ingested {count} chunks from {corpus_dir}")


if __name__ == "__main__":
    main()
