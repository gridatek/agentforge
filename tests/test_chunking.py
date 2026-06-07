"""Markdown-aware chunking — pure text, no embeddings, runs in CI without keys."""

from __future__ import annotations

from langchain_core.documents import Document

from agentforge.rag.chunking import split_documents

_MARKDOWN = """# Compliance Policy

## AML

Enhanced due diligence applies at $10,000.

## KYC

A passport and proof of address are required.
"""


def test_markdown_chunks_carry_section_metadata():
    doc = Document(page_content=_MARKDOWN, metadata={"source": "policy.md", "title": "Policy"})
    chunks = split_documents([doc])

    sections = {c.metadata.get("section") for c in chunks}
    assert "AML" in sections
    assert "KYC" in sections
    # Source metadata is preserved on every chunk.
    assert all(c.metadata["source"] == "policy.md" for c in chunks)
    # Header text is retained in the chunk content (strip_headers=False).
    assert any("$10,000" in c.page_content for c in chunks)


def test_plaintext_falls_back_to_character_splitter():
    doc = Document(
        page_content="No headers here, just a single line of plain text.",
        metadata={"source": "notes.txt", "title": "Notes"},
    )
    chunks = split_documents([doc])

    assert len(chunks) == 1
    assert chunks[0].metadata["source"] == "notes.txt"
    # Plain text has no markdown section.
    assert chunks[0].metadata.get("section", "") == ""
