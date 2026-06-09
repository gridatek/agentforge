"""Graph nodes — the units of work the agent executes.

A supervisor routes each request to one of two specialists, which keeps the
safety posture legible: the knowledge path can never trigger an action (no
tools are bound), and every action goes through the same human gate.

    guardrails → supervisor ─(knowledge)→ retrieve → answer ──────────────→ end
                            └(action)──→ act_agent ─(sensitive tool?)→ approval → act → end
                                                    └(otherwise)──────────────────────→ end

- ``guardrails`` strips PII before anything reaches a model or a trace.
- ``supervisor`` classifies the request as "knowledge" or "action".
- ``retrieve`` grounds the answer; an empty result drives a refusal.
- ``answer`` replies with citations — no tools bound, so it can't act.
- ``act_agent`` proposes a tool call for the requested operation.
- ``approval`` pauses the graph (durable) until a human approves/rejects.
- ``act`` runs the tool only after sign-off.
"""

from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.types import interrupt

from agentforge.agents.state import AgentState
from agentforge.agents.tools import TOOLS, execute_tool
from agentforge.config import get_settings
from agentforge.guardrails import redact_pii, requires_approval
from agentforge.llm import get_chat_model, get_fast_model
from agentforge.rag import retrieve

# Default persona (banking-compliance reference example). Override per-domain via
# the SYSTEM_PROMPT env / setting — see examples/.
SYSTEM_PROMPT = """You are AgentForge, a banking-compliance assistant.

Rules:
- Answer ONLY from the provided context. Cite sources inline as [1], [2], …
- If the context does not contain the answer, say you don't know and that the \
question is out of scope. Never invent policy, figures, or rules.
- For sensitive actions (escalating a case, filing a SAR), call the appropriate \
tool. A human will review before it runs — do not claim the action is done."""

# Router persona for the supervisor. Kept deliberately narrow: one word out.
ROUTER_PROMPT = """You route a user request to exactly one specialist. Reply with \
a single lowercase word and nothing else:
- "knowledge" — the user is asking a question to be answered from policy or \
reference documents.
- "action" — the user is asking you to perform a sensitive operation (for \
example escalating a case or filing a report).
When unsure, answer "knowledge"."""


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


def supervisor_node(state: AgentState) -> dict:
    """Classify the request and route it to a specialist.

    Uses the cheap/fast model (a one-word classification, not reasoning). The
    parse is forgiving and biased to "knowledge" — the safe default, since the
    knowledge path has no tools and so can never trigger an action.
    """
    model = get_fast_model()
    response = model.invoke(
        [SystemMessage(ROUTER_PROMPT), HumanMessage(state["redacted_question"])]
    )
    text = (response.content or "").strip().lower()
    route = "action" if "action" in text else "knowledge"
    return {"route": route}


def retrieve_node(state: AgentState) -> dict:
    result = retrieve(state["redacted_question"])
    return {
        "context": result.context_block(),
        "citations": [c.__dict__ for c in result.citations],
        "grounded": result.grounded,
    }


def answer_node(state: AgentState) -> dict:
    """Knowledge specialist: a grounded, cited answer with no tools bound.

    Because no tools are bound, this path is structurally incapable of
    proposing or running an action — the model can only answer or refuse.
    """
    model = get_chat_model()

    context = state.get("context") or "(no relevant context found)"
    grounding_note = (
        "Relevant context is below.\n\n" + context
        if state.get("grounded")
        else "No relevant context was found. Say you don't know and that the "
        "question is out of scope."
    )
    messages = [
        SystemMessage(get_settings().system_prompt or SYSTEM_PROMPT),
        SystemMessage(grounding_note),
        HumanMessage(state["redacted_question"]),
    ]
    response = model.invoke(messages)
    return {"messages": [response], "answer": response.content, "proposed_action": None}


def act_agent_node(state: AgentState) -> dict:
    """Action specialist: bind tools and propose the requested operation."""
    model = get_chat_model().bind_tools(TOOLS)
    messages = [
        SystemMessage(get_settings().system_prompt or SYSTEM_PROMPT),
        SystemMessage(
            "The user is requesting an action. If it requires a sensitive tool "
            "(escalating a case, filing a SAR), call the appropriate tool — a human "
            "will review before it runs, so do not claim it is done. If no tool "
            "applies, answer directly."
        ),
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
