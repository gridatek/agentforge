"""Document chunking.

Markdown documents are split **header-first** (so each chunk knows which
section it came from), then size-limited with a recursive character splitter
that breaks on semantic boundaries. Plain-text documents skip straight to the
character splitter. Every chunk keeps its source + section metadata so
retrieval can cite it precisely.
"""

from __future__ import annotations

from langchain_core.documents import Document
from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)

from agentforge.config import get_settings

_MARKDOWN_SUFFIXES = (".md", ".markdown")
_HEADERS = [("#", "h1"), ("##", "h2"), ("###", "h3")]


def _char_splitter() -> RecursiveCharacterTextSplitter:
    settings = get_settings()
    return RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
        add_start_index=True,
    )


def _split_markdown(doc: Document, char_splitter: RecursiveCharacterTextSplitter) -> list[Document]:
    # Headers kept in content (strip_headers=False) so the section title stays
    # available to the model when the chunk is retrieved.
    md_splitter = MarkdownHeaderTextSplitter(_HEADERS, strip_headers=False)
    sections = md_splitter.split_text(doc.page_content)
    for section in sections:
        section.metadata = {**doc.metadata, **section.metadata}
        # The deepest header present names the section; fall back to the title.
        section.metadata["section"] = (
            section.metadata.get("h3")
            or section.metadata.get("h2")
            or section.metadata.get("h1")
            or doc.metadata.get("title", "")
        )
    return char_splitter.split_documents(sections)


def split_documents(documents: list[Document]) -> list[Document]:
    char_splitter = _char_splitter()
    chunks: list[Document] = []
    for doc in documents:
        source = str(doc.metadata.get("source", "")).lower()
        if source.endswith(_MARKDOWN_SUFFIXES):
            chunks.extend(_split_markdown(doc, char_splitter))
        else:
            chunks.extend(char_splitter.split_documents([doc]))
    return chunks
