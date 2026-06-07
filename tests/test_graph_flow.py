"""End-to-end graph behavior: grounded answers, refusals, and inline tools."""

from __future__ import annotations

import agentforge.agents.nodes as nodes
from langchain_core.messages import AIMessage

from tests.fakes import FakeChatModel, empty_retrieval, grounded_retrieval


def _config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


def test_grounded_answer_includes_citations(fresh_graph, monkeypatch):
    monkeypatch.setattr(nodes, "retrieve", lambda q: grounded_retrieval())
    monkeypatch.setattr(
        nodes,
        "get_chat_model",
        lambda: FakeChatModel(responses=[AIMessage("EDD applies at $10,000 [1].")]),
    )

    result = fresh_graph.invoke(
        {"question": "When is enhanced due diligence required?"}, config=_config("g1")
    )

    assert result["grounded"] is True
    assert "[1]" in result["answer"]
    assert result["citations"][0]["source"] == "aml.md"
    assert "__interrupt__" not in result  # no approval needed


def test_out_of_scope_question_is_refused(fresh_graph, monkeypatch):
    monkeypatch.setattr(nodes, "retrieve", lambda q: empty_retrieval())
    monkeypatch.setattr(
        nodes,
        "get_chat_model",
        lambda: FakeChatModel(responses=[AIMessage("I don't know — that's out of scope.")]),
    )

    result = fresh_graph.invoke(
        {"question": "What is the capital of France?"}, config=_config("g2")
    )

    assert result["grounded"] is False
    assert result["citations"] == []
    assert "out of scope" in result["answer"].lower()
    assert "__interrupt__" not in result


def test_non_sensitive_tool_executes_without_approval(fresh_graph, monkeypatch):
    # Treat everything as non-sensitive for this test: the auto-exec path runs.
    monkeypatch.setattr(nodes, "requires_approval", lambda name: False)
    monkeypatch.setattr(nodes, "retrieve", lambda q: grounded_retrieval())
    tool_call = {
        "name": "escalate_case",
        "args": {"customer_ref": "C-1", "reason": "unusual activity"},
        "id": "call_1",
        "type": "tool_call",
    }
    monkeypatch.setattr(
        nodes,
        "get_chat_model",
        lambda: FakeChatModel(responses=[AIMessage(content="", tool_calls=[tool_call])]),
    )

    result = fresh_graph.invoke({"question": "Escalate C-1"}, config=_config("g3"))

    assert "escalated" in result["answer"].lower()
    assert "__interrupt__" not in result
