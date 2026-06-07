"""Grounded retrieval with citations.

The ``score_threshold`` is the mechanism behind *grounded refusals*: when no
chunk is close enough to the query, ``retrieve`` returns an empty result and the
agent is instructed to say it doesn't know rather than invent an answer.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from langchain_core.documents import Document

from agentforge.config import get_settings
from agentforge.rag.store import get_vector_store


@dataclass
class Citation:
    """A single retrieved chunk, traceable back to its source document."""

    source: str
    title: str
    snippet: str
    score: float  # cosine distance — lower is closer


@dataclass
class RetrievalResult:
    documents: list[Document] = field(default_factory=list)
    citations: list[Citation] = field(default_factory=list)

    @property
    def grounded(self) -> bool:
        """True when at least one sufficiently-relevant chunk was found."""
        return bool(self.documents)

    def context_block(self) -> str:
        """Render retrieved chunks as a numbered context block for the prompt."""
        parts = []
        for i, doc in enumerate(self.documents, start=1):
            source = doc.metadata.get("source", "unknown")
            parts.append(f"[{i}] (source: {source})\n{doc.page_content}")
        return "\n\n".join(parts)


def retrieve(query: str) -> RetrievalResult:
    settings = get_settings()
    store = get_vector_store()

    # PGVector returns (document, distance) pairs; distance is cosine distance,
    # so smaller means more similar.
    scored = store.similarity_search_with_score(query, k=settings.retrieval_k)

    result = RetrievalResult()
    for doc, distance in scored:
        if distance > settings.score_threshold:
            continue  # too far away — drop it (this is what enables refusals)
        result.documents.append(doc)
        result.citations.append(
            Citation(
                source=doc.metadata.get("source", "unknown"),
                title=doc.metadata.get("title", ""),
                snippet=doc.page_content[:240].strip(),
                score=round(float(distance), 4),
            )
        )
    return result
