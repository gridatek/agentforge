"""Shared fixtures for graph tests."""

from __future__ import annotations

import pytest


@pytest.fixture
def fresh_graph():
    """A freshly compiled graph with an isolated in-memory checkpointer.

    Built per-test so HITL checkpoint state never leaks between tests. The node
    functions resolve ``get_chat_model`` / ``retrieve`` from module globals at
    call time, so tests can monkeypatch those names to inject fakes.
    """
    from langgraph.checkpoint.memory import MemorySaver

    from agentforge.agents.graph import build_graph

    return build_graph().compile(checkpointer=MemorySaver())
