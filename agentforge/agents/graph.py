"""Assemble and compile the LangGraph.

The compiled graph is checkpointed, which gives us two things at once:
durable execution (a crash mid-run resumes from the last node) and the pause/
resume mechanics that human-in-the-loop approval relies on.

For production, swap ``MemorySaver`` for ``langgraph.checkpoint.postgres.PostgresSaver``
so checkpoints survive process restarts — same interface, persistent store.
"""

from __future__ import annotations

from functools import lru_cache

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from agentforge.agents.nodes import (
    act_node,
    approval_node,
    generate_node,
    guardrails_node,
    retrieve_node,
)
from agentforge.agents.state import AgentState


def _route_after_generate(state: AgentState) -> str:
    return "approval" if state.get("proposed_action") else "end"


def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)
    graph.add_node("guardrails", guardrails_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("generate", generate_node)
    graph.add_node("approval", approval_node)
    graph.add_node("act", act_node)

    graph.add_edge(START, "guardrails")
    graph.add_edge("guardrails", "retrieve")
    graph.add_edge("retrieve", "generate")
    graph.add_conditional_edges(
        "generate", _route_after_generate, {"approval": "approval", "end": END}
    )
    graph.add_edge("approval", "act")
    graph.add_edge("act", END)
    return graph


@lru_cache
def get_compiled_graph():
    """Compiled, checkpointed graph (cached as a process-wide singleton)."""
    return build_graph().compile(checkpointer=MemorySaver())
