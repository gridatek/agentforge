"""Provider-agnostic LLM layer — chat models and embeddings, swappable via config."""

from agentforge.llm.provider import get_chat_model, get_embeddings, get_fast_model

__all__ = ["get_chat_model", "get_fast_model", "get_embeddings"]
