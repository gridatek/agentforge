"""Supervisor routing: knowledge vs action, with a safe default.

These pin the structural guarantees of the split graph — the action path
never retrieves, the knowledge path never binds tools — and the forgiving
parse that biases an unrecognized classification back to "knowledge".
"""

from __future__ import annotations

import agentforge.agents.nodes as nodes
from langchain_core.messages import AIMessage

from tests.fakes import FakeChatModel, empty_retrieval


def _config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


def _no_retrieve(query: str, tenant_id=None):
    raise AssertionError("knowledge path was taken on an action request")


def test_action_request_routes_to_act_agent_without_retrieval(fresh_graph, monkeypatch):
    monkeypatch.setattr(nodes, "get_fast_model", lambda: FakeChatModel(responses=[AIMessage("action")]))
    # Retrieval must never run on the action path.
    monkeypatch.setattr(nodes, "retrieve", _no_retrieve)
    sar_call = {
        "name": "file_sar",
        "args": {"customer_ref": "C-2", "summary": "possible structuring"},
        "id": "call_x",
        "type": "tool_call",
    }
    monkeypatch.setattr(
        nodes,
        "get_chat_model",
        lambda: FakeChatModel(responses=[AIMessage(content="", tool_calls=[sar_call])]),
    )

    result = fresh_graph.invoke({"question": "File a SAR for C-2"}, config=_config("sup-act"))

    assert result["route"] == "action"
    assert result["proposed_action"]["name"] == "file_sar"
    assert "__interrupt__" in result  # paused for human approval


def test_unrecognized_classification_defaults_to_knowledge(fresh_graph, monkeypatch):
    # A garbage one-word reply must fall back to the safe (tool-less) path.
    monkeypatch.setattr(nodes, "get_fast_model", lambda: FakeChatModel(responses=[AIMessage("???")]))
    monkeypatch.setattr(nodes, "retrieve", lambda q, tenant_id=None: empty_retrieval())
    monkeypatch.setattr(
        nodes, "get_chat_model", lambda: FakeChatModel(responses=[AIMessage("Out of scope.")])
    )

    result = fresh_graph.invoke({"question": "anything"}, config=_config("sup-default"))

    assert result["route"] == "knowledge"
    assert result["proposed_action"] is None
