"""Assemble and compile the LangGraph.

The compiled graph is checkpointed, which gives us two things at once:
durable execution (a crash mid-run resumes from the last node) and the pause/
resume mechanics that human-in-the-loop approval relies on.

The backend is configurable: ``MemorySaver`` in-process by default (dev/tests),
or a durable ``PostgresSaver`` when ``CHECKPOINT_BACKEND=postgres`` (see
``checkpoint.py``) so checkpoints survive restarts and work across replicas.
"""

from __future__ import annotations

from functools import lru_cache

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from agentforge.agents.nodes import (
    act_agent_node,
    act_node,
    answer_node,
    approval_node,
    guardrails_node,
    retrieve_node,
    supervisor_node,
)
from agentforge.agents.state import AgentState


def _route_from_supervisor(state: AgentState) -> str:
    """Dispatch to the specialist the supervisor selected (default: knowledge)."""
    return "action" if state.get("route") == "action" else "knowledge"


def _route_after_action(state: AgentState) -> str:
    return "approval" if state.get("proposed_action") else "end"


def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)
    graph.add_node("guardrails", guardrails_node)
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("answer", answer_node)
    graph.add_node("act_agent", act_agent_node)
    graph.add_node("approval", approval_node)
    graph.add_node("act", act_node)

    graph.add_edge(START, "guardrails")
    graph.add_edge("guardrails", "supervisor")
    graph.add_conditional_edges(
        "supervisor",
        _route_from_supervisor,
        {"knowledge": "retrieve", "action": "act_agent"},
    )
    # Knowledge path: ground, answer, done.
    graph.add_edge("retrieve", "answer")
    graph.add_edge("answer", END)
    # Action path: propose a tool, gate sensitive ones through human approval.
    graph.add_conditional_edges(
        "act_agent", _route_after_action, {"approval": "approval", "end": END}
    )
    graph.add_edge("approval", "act")
    graph.add_edge("act", END)
    return graph


@lru_cache
def get_compiled_graph():
    """Compiled, checkpointed graph (cached as a process-wide singleton).

    Uses a durable Postgres checkpointer when ``CHECKPOINT_BACKEND=postgres``
    (set by docker-compose / k8s), otherwise the in-process ``MemorySaver``.
    """
    from agentforge.config import get_settings

    if get_settings().checkpoint_backend == "postgres":
        from agentforge.agents.checkpoint import get_postgres_checkpointer

        checkpointer = get_postgres_checkpointer()
    else:
        checkpointer = MemorySaver()
    return build_graph().compile(checkpointer=checkpointer)
