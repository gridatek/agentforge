"""The FastAPI gateway.

Endpoints:
- ``GET  /health``        liveness probe.
- ``POST /chat``          run the agent; may pause for approval.
- ``POST /chat/stream``   stream the answer token-by-token over SSE.
- ``POST /approve``       resume a paused run with approve/reject.

State persistence (including paused approvals) is handled by the graph's
checkpointer, keyed by ``thread_id``.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langgraph.types import Command
from sse_starlette.sse import EventSourceResponse

from agentforge.agents import get_compiled_graph
from agentforge.api.schemas import (
    ApprovalRequest,
    ChatRequest,
    ChatResponse,
    PendingAction,
)
from agentforge.config import get_settings
from agentforge.observability import get_callbacks, setup_observability

app = FastAPI(title="AgentForge", version="0.1.0")

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    setup_observability()


def _run_config(thread_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": thread_id}, "callbacks": get_callbacks()}


def _extract_interrupt(result: dict[str, Any]) -> dict[str, Any] | None:
    """Return the interrupt payload if the graph paused, else None."""
    interrupts = result.get("__interrupt__")
    if not interrupts:
        return None
    first = interrupts[0]
    return getattr(first, "value", first)


def _to_response(thread_id: str, result: dict[str, Any]) -> ChatResponse:
    interrupt = _extract_interrupt(result)
    if interrupt:
        action = interrupt.get("action", {})
        return ChatResponse(
            thread_id=thread_id,
            approval_required=True,
            pending_action=PendingAction(**action),
            pii_found=result.get("pii_found", []),
        )
    return ChatResponse(
        thread_id=thread_id,
        answer=result.get("answer"),
        citations=result.get("citations", []),
        pii_found=result.get("pii_found", []),
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    thread_id = req.thread_id or str(uuid.uuid4())
    graph = get_compiled_graph()
    result = graph.invoke({"question": req.message}, config=_run_config(thread_id))
    return _to_response(thread_id, result)


@app.post("/approve", response_model=ChatResponse)
def approve(req: ApprovalRequest) -> ChatResponse:
    graph = get_compiled_graph()
    result = graph.invoke(
        Command(resume=req.decision), config=_run_config(req.thread_id)
    )
    return _to_response(req.thread_id, result)


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest) -> EventSourceResponse:
    thread_id = req.thread_id or str(uuid.uuid4())
    graph = get_compiled_graph()
    config = _run_config(thread_id)

    async def event_generator():
        yield {"event": "thread", "data": thread_id}
        # Stream LLM tokens as they are produced by the generate node.
        async for event in graph.astream_events(
            {"question": req.message}, config=config, version="v2"
        ):
            if event["event"] == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                if getattr(chunk, "content", ""):
                    yield {"event": "token", "data": chunk.content}
        # Emit final state (answer, citations, or approval request).
        snapshot = graph.get_state(config)
        values = snapshot.values
        if snapshot.next:  # paused at an interrupt
            yield {"event": "approval_required", "data": str(values.get("proposed_action"))}
        else:
            yield {"event": "done", "data": values.get("answer", "")}

    return EventSourceResponse(event_generator())
