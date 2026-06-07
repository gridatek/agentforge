"""Document chunking.

A recursive character splitter that tries to break on semantic boundaries
(paragraphs, then lines, then sentences) before falling back to hard cuts.
Each chunk keeps its source metadata so retrieval can cite it.
"""

from __future__ import annotations

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from agentforge.config import get_settings


def split_documents(documents: list[Document]) -> list[Document]:
    settings = get_settings()
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
        add_start_index=True,
    )
    return splitter.split_documents(documents)
