"""Observability backend selection. No external services or langfuse install."""

from __future__ import annotations

import os

import pytest

from agentforge.config import get_settings
from agentforge.observability import tracing


@pytest.fixture(autouse=True)
def _clear_callbacks_cache():
    # get_callbacks is lru_cached; reset around each test so backend changes apply.
    tracing.get_callbacks.cache_clear()
    yield
    tracing.get_callbacks.cache_clear()


def test_no_callbacks_for_none_or_langsmith(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "observability_backend", "none")
    assert tracing.get_callbacks() == []

    tracing.get_callbacks.cache_clear()
    monkeypatch.setattr(settings, "observability_backend", "langsmith")
    assert tracing.get_callbacks() == []


def test_langfuse_backend_requires_extra(monkeypatch):
    # langfuse isn't in the dev install, so selecting it must raise a helpful error.
    monkeypatch.setattr(get_settings(), "observability_backend", "langfuse")
    with pytest.raises(RuntimeError, match="langfuse"):
        tracing.get_callbacks()


def test_setup_langsmith_exports_env(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "observability_backend", "langsmith")
    monkeypatch.setattr(settings, "langchain_api_key", "ls-test")
    monkeypatch.delenv("LANGCHAIN_TRACING_V2", raising=False)

    tracing.setup_observability()
    assert os.environ["LANGCHAIN_TRACING_V2"] == "true"
    assert os.environ["LANGCHAIN_API_KEY"] == "ls-test"

    for key in ("LANGCHAIN_TRACING_V2", "LANGCHAIN_API_KEY"):
        os.environ.pop(key, None)


def test_setup_langfuse_exports_env(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "observability_backend", "langfuse")
    monkeypatch.setattr(settings, "langfuse_public_key", "pk-test")
    monkeypatch.setattr(settings, "langfuse_secret_key", "sk-test")
    monkeypatch.setattr(settings, "langfuse_host", "http://langfuse:3000")

    tracing.setup_observability()
    assert os.environ["LANGFUSE_PUBLIC_KEY"] == "pk-test"
    assert os.environ["LANGFUSE_SECRET_KEY"] == "sk-test"
    assert os.environ["LANGFUSE_HOST"] == "http://langfuse:3000"

    for key in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_HOST"):
        os.environ.pop(key, None)
