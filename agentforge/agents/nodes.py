"""Graph nodes — the units of work the agent executes.

The flow encodes the platform's safety posture:

    guardrails → retrieve → generate ──(sensitive tool?)──→ approval → act
                                     └──(otherwise)─────────────────────→ end

- ``guardrails`` strips PII before anything reaches the model or a trace.
- ``retrieve`` grounds the answer; an empty result drives a refusal.
- ``generate`` answers with citations, or proposes a sensitive tool call.
- ``approval`` pauses the graph (durable) until a human approves/rejects.
- ``act`` runs the tool only after sign-off.
"""

from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.types import interrupt

from agentforge.agents.state import AgentState
from agentforge.agents.tools import TOOLS, execute_tool
from agentforge.guardrails import redact_pii, requires_approval
from agentforge.llm import get_chat_model
from agentforge.rag import retrieve

SYSTEM_PROMPT = """You are AgentForge, a banking-compliance assistant.

Rules:
- Answer ONLY from the provided context. Cite sources inline as [1], [2], …
- If the context does not contain the answer, say you don't know and that the \
question is out of scope. Never invent policy, figures, or rules.
- For sensitive actions (escalating a case, filing a SAR), call the appropriate \
tool. A human will review before it runs — do not claim the action is done."""


def _latest_question(state: AgentState) -> str:
    """Prefer an explicit ``question``; otherwise the last human message."""
    if state.get("question"):
        return state["question"]
    for msg in reversed(state.get("messages", [])):
        if isinstance(msg, HumanMessage):
            return msg.content
    return ""


def guardrails_node(state: AgentState) -> dict:
    question = _latest_question(state)
    redacted, found = redact_pii(question)
    return {"question": question, "redacted_question": redacted, "pii_found": found}


def retrieve_node(state: AgentState) -> dict:
    result = retrieve(state["redacted_question"])
    return {
        "context": result.context_block(),
        "citations": [c.__dict__ for c in result.citations],
        "grounded": result.grounded,
    }


def generate_node(state: AgentState) -> dict:
    model = get_chat_model().bind_tools(TOOLS)

    context = state.get("context") or "(no relevant context found)"
    grounding_note = (
        "Relevant context is below.\n\n" + context
        if state.get("grounded")
        else "No relevant context was found. Refuse and mark the question out of scope, "
        "unless the user is requesting a sensitive action."
    )
    messages = [
        SystemMessage(SYSTEM_PROMPT),
        SystemMessage(grounding_note),
        HumanMessage(state["redacted_question"]),
    ]
    response = model.invoke(messages)

    tool_calls = getattr(response, "tool_calls", []) or []
    if tool_calls:
        call = tool_calls[0]
        action = {
            "id": call.get("id"),
            "name": call["name"],
            "args": call.get("args", {}),
        }
        # Sensitive tools hand off to human approval before running.
        if requires_approval(action["name"]):
            return {"messages": [response], "proposed_action": action}
        # Non-sensitive tools execute immediately — no human gate needed.
        result = execute_tool(action["name"], action["args"])
        return {
            "messages": [response, ToolMessage(result, tool_call_id=action["id"])],
            "answer": result,
            "proposed_action": None,
        }

    return {"messages": [response], "answer": response.content, "proposed_action": None}


def approval_node(state: AgentState) -> dict:
    """Pause for human-in-the-loop sign-off.

    ``interrupt`` suspends the graph and persists state via the checkpointer;
    execution resumes when the caller sends ``Command(resume="approve"|"reject")``.
    """
    action = state["proposed_action"]
    decision = interrupt(
        {
            "type": "approval_request",
            "action": action,
            "question": state.get("question", ""),
        }
    )
    # ``decision`` is whatever the human passed to resume the graph.
    if isinstance(decision, dict):
        decision = decision.get("decision", "reject")
    return {"approval_decision": decision}


def act_node(state: AgentState) -> dict:
    action = state["proposed_action"] or {}
    if state.get("approval_decision") == "approve":
        result = execute_tool(action["name"], action.get("args", {}))
        answer = f"Action approved and executed: {result}"
    else:
        answer = (
            f"The requested action `{action.get('name')}` was not approved, "
            "so it was not performed."
        )
    return {"answer": answer, "messages": [AIMessage(answer)], "proposed_action": None}
