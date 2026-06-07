"""The provider-agnostic LLM layer.

A single seam through which the whole platform talks to a model. Swap
``CHAT_MODEL`` / ``EMBEDDING_MODEL`` in the environment to move between Claude,
OpenAI, and local Ollama without touching application code.

We lean on LangChain's ``init_chat_model`` / ``init_embeddings`` factories,
which parse a ``"provider:model"`` string and return the right integration.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from langchain.chat_models import init_chat_model
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel

from agentforge.config import get_settings


def _provider_kwargs(model_string: str) -> dict[str, Any]:
    """Inject provider-specific connection settings (keys, base URLs)."""
    settings = get_settings()
    provider = model_string.split(":", 1)[0] if ":" in model_string else ""
    kwargs: dict[str, Any] = {}
    if provider == "anthropic" and settings.anthropic_api_key:
        kwargs["api_key"] = settings.anthropic_api_key
    elif provider == "openai" and settings.openai_api_key:
        kwargs["api_key"] = settings.openai_api_key
    elif provider == "ollama":
        kwargs["base_url"] = settings.ollama_base_url
    return kwargs


@lru_cache
def get_chat_model() -> BaseChatModel:
    """The primary reasoning model (defaults to ``claude-opus-4-8``)."""
    settings = get_settings()
    return init_chat_model(
        settings.chat_model,
        max_tokens=settings.max_tokens,
        **_provider_kwargs(settings.chat_model),
    )


@lru_cache
def get_fast_model() -> BaseChatModel:
    """A cheaper/faster model for planning, routing, and grading."""
    settings = get_settings()
    return init_chat_model(
        settings.fast_model,
        max_tokens=settings.max_tokens,
        **_provider_kwargs(settings.fast_model),
    )


@lru_cache
def get_embeddings() -> Embeddings:
    """Embeddings model used for ingestion and retrieval.

    Imported lazily so the chat path doesn't pull in embedding integrations.
    """
    from langchain.embeddings import init_embeddings  # local import: optional dep surface

    settings = get_settings()
    return init_embeddings(
        settings.embedding_model,
        **_provider_kwargs(settings.embedding_model),
    )
