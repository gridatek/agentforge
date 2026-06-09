"""Human-in-the-loop: a sensitive tool pauses the graph until a human decides."""

from __future__ import annotations

import agentforge.agents.nodes as nodes
from langchain_core.messages import AIMessage
from langgraph.types import Command

from tests.fakes import FakeChatModel, route_model

_SAR_CALL = {
    "name": "file_sar",
    "args": {"customer_ref": "C-9", "summary": "possible structuring"},
    "id": "call_sar",
    "type": "tool_call",
}


def _setup(monkeypatch):
    monkeypatch.setattr(nodes, "get_fast_model", lambda: route_model("action"))
    monkeypatch.setattr(
        nodes,
        "get_chat_model",
        lambda: FakeChatModel(responses=[AIMessage(content="", tool_calls=[_SAR_CALL])]),
    )


def test_sensitive_tool_pauses_for_approval(fresh_graph, monkeypatch):
    _setup(monkeypatch)
    config = {"configurable": {"thread_id": "hitl-pause"}}

    first = fresh_graph.invoke({"question": "File a SAR for C-9"}, config=config)

    assert "__interrupt__" in first  # graph paused
    assert first["proposed_action"]["name"] == "file_sar"


def test_approve_executes_the_action(fresh_graph, monkeypatch):
    _setup(monkeypatch)
    config = {"configurable": {"thread_id": "hitl-approve"}}

    fresh_graph.invoke({"question": "File a SAR for C-9"}, config=config)
    final = fresh_graph.invoke(Command(resume="approve"), config=config)

    assert "SAR drafted" in final["answer"]
    assert final["proposed_action"] is None


def test_reject_does_not_execute(fresh_graph, monkeypatch):
    _setup(monkeypatch)
    config = {"configurable": {"thread_id": "hitl-reject"}}

    fresh_graph.invoke({"question": "File a SAR for C-9"}, config=config)
    final = fresh_graph.invoke(Command(resume="reject"), config=config)

    assert "not approved" in final["answer"].lower()
    assert "SAR drafted" not in final["answer"]
