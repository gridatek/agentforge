"""Tracing adapter.

One switch (``OBSERVABILITY_BACKEND``) selects where traces go:

- ``langsmith`` — set env vars; LangChain auto-traces every node/LLM call.
- ``langfuse``  — return a callback handler for a fully self-hosted backend.
- ``none``      — no-op (default for local dev / tests).

Callers fetch callbacks via ``get_callbacks()`` and pass them in the run config.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from agentforge.config import get_settings


def setup_observability() -> None:
    """Configure the selected backend. Safe to call once at startup."""
    settings = get_settings()
    backend = settings.observability_backend.lower()

    if backend == "langsmith" and settings.langchain_api_key:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = settings.langchain_api_key
        os.environ["LANGCHAIN_PROJECT"] = settings.langchain_project

    elif backend == "langfuse":
        # Export the standard LANGFUSE_* vars so the SDK/handler pick them up
        # (works against Langfuse cloud or a self-hosted instance via the host).
        for var, value in (
            ("LANGFUSE_PUBLIC_KEY", settings.langfuse_public_key),
            ("LANGFUSE_SECRET_KEY", settings.langfuse_secret_key),
            ("LANGFUSE_HOST", settings.langfuse_host),
        ):
            if value:
                os.environ[var] = value


@lru_cache
def get_callbacks() -> list[Any]:
    """Run callbacks for the active backend (empty for langsmith/none).

    For langfuse, return its LangChain ``CallbackHandler`` so every node/LLM call
    is traced. Auth comes from the ``LANGFUSE_*`` env exported by
    ``setup_observability`` (or already in the environment).
    """
    settings = get_settings()
    if settings.observability_backend.lower() != "langfuse":
        return []

    try:
        from langfuse.callback import CallbackHandler
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "OBSERVABILITY_BACKEND=langfuse requires the 'langfuse' extra: "
            "pip install 'agentforge[langfuse]'"
        ) from exc

    # Pass explicit credentials when configured; otherwise the handler falls back
    # to the LANGFUSE_* environment.
    kwargs = {
        k: v
        for k, v in (
            ("public_key", settings.langfuse_public_key),
            ("secret_key", settings.langfuse_secret_key),
            ("host", settings.langfuse_host),
        )
        if v
    }
    return [CallbackHandler(**kwargs)]
