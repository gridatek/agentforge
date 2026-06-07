"""PII must be redacted before the question reaches retrieval or the model."""

from __future__ import annotations

import agentforge.agents.nodes as nodes
from langchain_core.messages import AIMessage

from tests.fakes import FakeChatModel, empty_retrieval


def test_pii_redacted_before_retrieval(fresh_graph, monkeypatch):
    seen: dict[str, str] = {}

    def spy_retrieve(query: str):
        seen["query"] = query
        return empty_retrieval()

    monkeypatch.setattr(nodes, "retrieve", spy_retrieve)
    monkeypatch.setattr(
        nodes, "get_chat_model", lambda: FakeChatModel(responses=[AIMessage("ok")])
    )

    result = fresh_graph.invoke(
        {"question": "My email is jane@example.com, am I verified?"},
        config={"configurable": {"thread_id": "pii-1"}},
    )

    # Retrieval saw the redacted form, not the raw email.
    assert "jane@example.com" not in seen["query"]
    assert "[REDACTED_EMAIL]" in seen["query"]
    assert "email" in result["pii_found"]
