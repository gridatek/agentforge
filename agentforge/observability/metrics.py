"""Prometheus metrics.

Exposes process metrics plus a few AgentForge-specific counters at ``/metrics``
(wired in the FastAPI app). The API runs single-worker (see the Dockerfile), so
the default global registry is correct — no multiprocess collector needed.
"""

from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

# --- HTTP layer (incremented by middleware) ------------------------------
http_requests_total = Counter(
    "agentforge_http_requests_total",
    "HTTP requests handled.",
    ["method", "path", "status"],
)
http_request_duration_seconds = Histogram(
    "agentforge_http_request_duration_seconds",
    "HTTP request latency.",
    ["method", "path"],
)

# --- Domain layer (incremented by the chat/approve handlers) -------------
chat_requests_total = Counter(
    "agentforge_chat_requests_total",
    "Chat requests received.",
)
answers_total = Counter(
    "agentforge_answers_total",
    "Answers produced, labelled by whether they were grounded in retrieved context.",
    ["grounded"],
)
approvals_total = Counter(
    "agentforge_approvals_total",
    "Human approval decisions on sensitive actions.",
    ["decision"],
)
pii_redactions_total = Counter(
    "agentforge_pii_redactions_total",
    "PII spans redacted from inbound messages, by type.",
    ["label"],
)


def render() -> tuple[bytes, str]:
    """Return ``(payload, content_type)`` for the /metrics response."""
    return generate_latest(), CONTENT_TYPE_LATEST
