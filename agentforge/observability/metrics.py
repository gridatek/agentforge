"""Prometheus metrics.

Exposes process metrics plus a few AgentForge-specific counters at ``/metrics``
(wired in the FastAPI app). The API runs single-worker (see the Dockerfile), so
the default global registry is correct — no multiprocess collector needed.
"""

from __future__ import annotations

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

# Counter names omit the `_total` suffix on purpose — prometheus_client appends
# it automatically, so e.g. `agentforge_chat_requests` is exported as
# `agentforge_chat_requests_total`. (Including it here would double it.)

# --- HTTP layer (incremented by middleware) ------------------------------
http_requests_total = Counter(
    "agentforge_http_requests",
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
    "agentforge_chat_requests",
    "Chat requests received.",
)
answers_total = Counter(
    "agentforge_answers",
    "Answers produced, labelled by whether they were grounded in retrieved context.",
    ["grounded"],
)
approvals_total = Counter(
    "agentforge_approvals",
    "Human approval decisions on sensitive actions.",
    ["decision"],
)
pii_redactions_total = Counter(
    "agentforge_pii_redactions",
    "PII spans redacted from inbound messages, by type.",
    ["label"],
)
pending_approvals = Gauge(
    "agentforge_pending_approvals",
    "Sensitive actions currently paused awaiting human approval.",
)


def render() -> tuple[bytes, str]:
    """Return ``(payload, content_type)`` for the /metrics response."""
    return generate_latest(), CONTENT_TYPE_LATEST
