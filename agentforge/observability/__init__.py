"""Pluggable observability: LangSmith by default, Langfuse for fully self-hosted."""

from agentforge.observability.tracing import get_callbacks, setup_observability

__all__ = ["setup_observability", "get_callbacks"]
