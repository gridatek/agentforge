"""The FastAPI gateway.

Endpoints:
- ``GET  /health``        liveness probe.
- ``GET  /metrics``       Prometheus metrics (HTTP + domain counters).
- ``GET  /documents``     list ingested source documents + chunk counts.
- ``GET  /evals``         latest eval report (or null if not run).
- ``GET  /approvals``     list runs paused awaiting human approval.
- ``POST /chat``          run the agent; may pause for approval.
- ``POST /chat/stream``   stream the answer token-by-token over SSE.
- ``POST /approve``       resume a paused run with approve/reject.

State persistence (including paused approvals) is handled by the graph's
checkpointer, keyed by ``thread_id``.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from langgraph.types import Command
from sse_starlette.sse import EventSourceResponse

from agentforge.agents import get_compiled_graph
from agentforge.api import approvals
from agentforge.api.schemas import (
    ApprovalRequest,
    ChatRequest,
    ChatResponse,
    DocumentSummaryItem,
    EvalReport,
    PendingAction,
    PendingApprovalItem,
)
from agentforge.api.tenancy import resolve_tenant, scoped_thread, validate_thread_id
from agentforge.config import get_settings
from agentforge.observability import get_callbacks, metrics, setup_observability

logger = logging.getLogger("agentforge.api")
settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    setup_observability()
    # Stamp any pre-multitenancy (untagged) chunks as the default tenant so an
    # existing single-tenant corpus keeps answering with zero re-ingest.
    try:
        from agentforge.rag.store import backfill_tenant

        stamped = backfill_tenant(settings.default_tenant)
        if stamped:
            logger.info(
                "Backfilled %d untagged chunks to tenant %r", stamped, settings.default_tenant
            )
    except Exception:
        logger.warning("Tenant backfill skipped (store not ready)", exc_info=True)
    if settings.auto_ingest:
        try:
            from agentforge.rag.ingest import ingest_if_empty

            count = ingest_if_empty(settings.auto_ingest_corpus)
            if count:
                logger.info(
                    "Auto-ingested %d chunks from %s", count, settings.auto_ingest_corpus
                )
        except Exception:
            # Never let an ingest hiccup take down the API — log and serve.
            logger.warning("Auto-ingest skipped (store/model not ready)", exc_info=True)
    yield


app = FastAPI(title="AgentForge", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def _metrics_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    # Label by route template (set on the scope during routing), not the raw
    # path, to keep label cardinality bounded. Unmatched paths are bucketed.
    route = request.scope.get("route")
    path = getattr(route, "path", "<unmatched>")
    if path != "/metrics":
        metrics.http_request_duration_seconds.labels(request.method, path).observe(
            time.perf_counter() - start
        )
        metrics.http_requests_total.labels(
            request.method, path, response.status_code
        ).inc()
    return response


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


@app.get("/metrics")
def prometheus_metrics() -> Response:
    payload, content_type = metrics.render()
    return Response(content=payload, media_type=content_type)


def _record_domain_metrics(resp: ChatResponse) -> None:
    """Translate a chat/approve result into domain counters."""
    for label in resp.pii_found:
        metrics.pii_redactions_total.labels(label).inc()
    if not resp.approval_required:
        grounded = "true" if resp.citations else "false"
        metrics.answers_total.labels(grounded).inc()


@app.get("/evals", response_model=EvalReport | None)
def evals() -> EvalReport | None:
    from agentforge.api.evals import load_report

    report = load_report()
    return EvalReport(**report) if report else None


@app.get("/documents", response_model=list[DocumentSummaryItem])
def documents(tenant: str = Depends(resolve_tenant)) -> list[DocumentSummaryItem]:
    from agentforge.rag.catalog import list_documents

    return [
        DocumentSummaryItem(source=d.source, title=d.title, chunks=d.chunks)
        for d in list_documents(tenant)
    ]


@app.get("/approvals", response_model=list[PendingApprovalItem])
def approval_queue(tenant: str = Depends(resolve_tenant)) -> list[PendingApprovalItem]:
    return [
        PendingApprovalItem(
            tenant_id=p.tenant_id,
            thread_id=p.thread_id,
            question=p.question,
            created_at=p.created_at,
            action=p.action,
        )
        for p in approvals.list_pending(tenant)
    ]


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest, tenant: str = Depends(resolve_tenant)) -> ChatResponse:
    metrics.chat_requests_total.inc()
    thread_id = validate_thread_id(req.thread_id) if req.thread_id else str(uuid.uuid4())
    graph = get_compiled_graph()
    result = graph.invoke(
        {"question": req.message, "tenant_id": tenant},
        config=_run_config(scoped_thread(tenant, thread_id)),
    )
    resp = _to_response(thread_id, result)
    _record_domain_metrics(resp)
    if resp.approval_required and resp.pending_action:
        approvals.register(tenant, thread_id, resp.pending_action, req.message)
    return resp


@app.post("/approve", response_model=ChatResponse)
def approve(req: ApprovalRequest, tenant: str = Depends(resolve_tenant)) -> ChatResponse:
    metrics.approvals_total.labels(req.decision).inc()
    thread_id = validate_thread_id(req.thread_id)
    graph = get_compiled_graph()
    result = graph.invoke(
        Command(resume=req.decision), config=_run_config(scoped_thread(tenant, thread_id))
    )
    approvals.resolve(tenant, thread_id)
    resp = _to_response(thread_id, result)
    _record_domain_metrics(resp)
    return resp


@app.post("/chat/stream")
async def chat_stream(
    req: ChatRequest, tenant: str = Depends(resolve_tenant)
) -> EventSourceResponse:
    thread_id = validate_thread_id(req.thread_id) if req.thread_id else str(uuid.uuid4())
    graph = get_compiled_graph()
    config = _run_config(scoped_thread(tenant, thread_id))

    # Only stream tokens from the answer-producing specialists — never the
    # supervisor, whose model emits a one-word routing label, not user output.
    _streaming_nodes = {"answer", "act_agent"}

    async def event_generator():
        yield {"event": "thread", "data": thread_id}
        # Stream LLM tokens as the answer/act_agent specialists produce them.
        async for event in graph.astream_events(
            {"question": req.message, "tenant_id": tenant}, config=config, version="v2"
        ):
            if event["event"] == "on_chat_model_stream":
                if event["metadata"].get("langgraph_node") not in _streaming_nodes:
                    continue
                chunk = event["data"]["chunk"]
                if getattr(chunk, "content", ""):
                    yield {"event": "token", "data": chunk.content}
        # Emit final state (answer, citations, or approval request).
        snapshot = graph.get_state(config)
        values = snapshot.values
        if snapshot.next:  # paused at an interrupt
            action = values.get("proposed_action") or {}
            if action:
                approvals.register(tenant, thread_id, PendingAction(**action), req.message)
            yield {
                "event": "approval_required",
                "data": json.dumps(action),
            }
        else:
            yield {
                "event": "done",
                "data": json.dumps(
                    {
                        "answer": values.get("answer", ""),
                        "citations": values.get("citations", []),
                        "pii_found": values.get("pii_found", []),
                    }
                ),
            }

    return EventSourceResponse(event_generator())
