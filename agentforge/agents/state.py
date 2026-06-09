"""Graph state.

Kept JSON-serializable (plain dicts/lists/strings) so it round-trips cleanly
through the LangGraph checkpointer for durable execution.
"""

from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langgraph.graph.message import add_messages


class AgentState(TypedDict, total=False):
    # Full chat history; ``add_messages`` reducer appends rather than replaces.
    messages: Annotated[list, add_messages]

    # The user's latest question, and its PII-redacted form used downstream.
    question: str
    redacted_question: str
    pii_found: list[str]

    # Supervisor routing decision: "knowledge" (answer from docs) | "action"
    # (perform a sensitive operation). Set by ``supervisor_node``.
    route: str

    # Retrieval output.
    context: str
    citations: list[dict[str, Any]]
    grounded: bool

    # A sensitive tool the model wants to run, awaiting human approval.
    proposed_action: dict[str, Any] | None
    approval_decision: str | None  # "approve" | "reject" | None

    # Final assistant answer.
    answer: str
