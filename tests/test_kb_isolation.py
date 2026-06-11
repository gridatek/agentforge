"""Per-tenant knowledge-base isolation (step 2).

Offline coverage of the tag-on-write / filter-on-read seam: ingest stamps every
chunk with the tenant, retrieval forwards a tenant-scoped filter to the store,
the graph threads the tenant through, and the pgvector filter has the shape the
backend expects. No real Postgres/Qdrant is needed — a recording fake store
stands in for the backend.
"""

from __future__ import annotations

from langchain_core.documents import Document

from agentforge.agents import nodes
from agentforge.rag import ingest as ingest_mod
from agentforge.rag import retriever as retriever_mod
from agentforge.rag import store


class _RecordingStore:
    """Captures add_documents chunks and the filter passed to retrieval."""

    def __init__(self, scored=None):
        self.added: list[Document] = []
        self.last_filter = "<unset>"
        self._scored = scored or []

    def add_documents(self, chunks):
        self.added.extend(chunks)

    def similarity_search_with_relevance_scores(self, query, k, filter=None):
        self.last_filter = filter
        return self._scored


def test_ingest_tags_every_chunk_with_tenant(monkeypatch):
    fake = _RecordingStore()
    monkeypatch.setattr(ingest_mod, "get_vector_store", lambda: fake)
    monkeypatch.setattr(
        ingest_mod,
        "load_corpus",
        lambda _dir: [Document(page_content="hello world", metadata={"source": "s", "title": "t"})],
    )

    count = ingest_mod.ingest("ignored", tenant_id="acme")

    assert count == len(fake.added) >= 1
    assert {c.metadata["tenant_id"] for c in fake.added} == {"acme"}


def test_ingest_defaults_to_default_tenant(monkeypatch):
    fake = _RecordingStore()
    monkeypatch.setattr(ingest_mod, "get_vector_store", lambda: fake)
    monkeypatch.setattr(
        ingest_mod, "load_corpus", lambda _dir: [Document(page_content="x", metadata={})]
    )

    ingest_mod.ingest("ignored")  # no tenant given

    from agentforge.config import get_settings

    assert {c.metadata["tenant_id"] for c in fake.added} == {get_settings().default_tenant}


def test_retrieve_forwards_tenant_filter(monkeypatch):
    fake = _RecordingStore(scored=[])
    monkeypatch.setattr(retriever_mod, "get_vector_store", lambda: fake)

    retriever_mod.retrieve("q", tenant_id="acme")

    # pgvector is the default backend in CI -> Mongo-style operator dict.
    assert fake.last_filter == {"tenant_id": {"$eq": "acme"}}


def test_retrieve_uses_default_tenant_when_unset(monkeypatch):
    fake = _RecordingStore(scored=[])
    monkeypatch.setattr(retriever_mod, "get_vector_store", lambda: fake)

    retriever_mod.retrieve("q")  # no tenant

    from agentforge.config import get_settings

    assert fake.last_filter == {"tenant_id": {"$eq": get_settings().default_tenant}}


def test_retrieve_node_threads_tenant_from_state(monkeypatch):
    seen = {}

    def fake_retrieve(query, tenant_id=None):
        seen["query"] = query
        seen["tenant"] = tenant_id
        return retriever_mod.RetrievalResult()

    monkeypatch.setattr(nodes, "retrieve", fake_retrieve)

    nodes.retrieve_node({"redacted_question": "q", "tenant_id": "globex"})

    assert seen == {"query": "q", "tenant": "globex"}


def test_pgvector_tenant_filter_shape():
    # Default backend is pgvector; the filter is the jsonb operator dict.
    assert store.tenant_filter("acme") == {"tenant_id": {"$eq": "acme"}}
