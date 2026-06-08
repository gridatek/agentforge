"""Vector-store backend selection. No DB/Qdrant available, so this covers the
default, the unknown-backend guard, and the missing-extra / graceful paths."""

from __future__ import annotations

import pytest

from agentforge.config import Settings, get_settings
from agentforge.rag import catalog, store


@pytest.fixture(autouse=True)
def _clear_store_cache():
    store.get_vector_store.cache_clear()
    yield
    store.get_vector_store.cache_clear()


def test_default_backend_is_pgvector():
    assert Settings().vector_store_backend == "pgvector"


def test_unknown_backend_raises(monkeypatch):
    monkeypatch.setattr(get_settings(), "vector_store_backend", "weaviate")
    with pytest.raises(ValueError, match="Unknown VECTOR_STORE_BACKEND"):
        store.get_vector_store()


def test_qdrant_backend_requires_extra(monkeypatch):
    # qdrant isn't in the dev install, so selecting it must raise a helpful error.
    monkeypatch.setattr(get_settings(), "vector_store_backend", "qdrant")
    with pytest.raises(RuntimeError, match="qdrant"):
        store.get_vector_store()


def test_catalog_empty_when_qdrant_unavailable(monkeypatch):
    # No qdrant-client installed -> the scroll import fails -> graceful empty list.
    monkeypatch.setattr(get_settings(), "vector_store_backend", "qdrant")
    assert catalog.list_documents() == []
