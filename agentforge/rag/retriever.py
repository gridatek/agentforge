"""Grounded retrieval with citations.

The ``min_relevance`` floor is the mechanism behind *grounded refusals*: when no
chunk is similar enough to the query, ``retrieve`` returns an empty result and
the agent is instructed to say it doesn't know rather than invent an answer.

Scores are normalized relevance in ``[0, 1]`` (higher = closer) rather than raw
distance, so the threshold reads intuitively and the UI can show a confidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from langchain_core.documents import Document

from agentforge.config import get_settings
from agentforge.rag.store import get_vector_store


@dataclass
class Citation:
    """A single retrieved chunk, traceable back to its source document/section."""

    source: str
    title: str
    snippet: str
    score: float  # normalized relevance in [0, 1] — higher is more relevant
    section: str = ""


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
            section = doc.metadata.get("section", "")
            header = f"[{i}] (source: {source}" + (f" › {section}" if section else "") + ")"
            parts.append(f"{header}\n{doc.page_content}")
        return "\n\n".join(parts)


def retrieve(query: str) -> RetrievalResult:
    settings = get_settings()
    store = get_vector_store()

    # Normalized relevance in [0, 1]; higher means more similar.
    scored = store.similarity_search_with_relevance_scores(query, k=settings.retrieval_k)

    result = RetrievalResult()
    for doc, relevance in scored:
        if relevance < settings.min_relevance:
            continue  # not relevant enough — drop it (this is what enables refusals)
        result.documents.append(doc)
        result.citations.append(
            Citation(
                source=doc.metadata.get("source", "unknown"),
                title=doc.metadata.get("title", ""),
                section=doc.metadata.get("section", ""),
                snippet=doc.page_content[:240].strip(),
                score=round(float(relevance), 4),
            )
        )
    return result
