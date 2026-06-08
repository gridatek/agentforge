"""Metrics endpoint + counters. Boots the FastAPI app via TestClient but never
invokes the LLM, so it needs no API keys or services."""

from __future__ import annotations

from fastapi.testclient import TestClient

from agentforge.api.main import app
from agentforge.observability import metrics


def test_health_and_metrics_exposed():
    client = TestClient(app)
    assert client.get("/health").json() == {"status": "ok"}

    resp = client.get("/metrics")
    assert resp.status_code == 200
    body = resp.text
    # The middleware should have recorded the /health request above.
    assert "agentforge_http_requests_total" in body
    assert "agentforge_http_request_duration_seconds" in body
    # /metrics scrapes are excluded to avoid self-inflating the counters.
    assert 'path="/metrics"' not in body


def test_domain_counters_render():
    metrics.chat_requests_total.inc()
    metrics.answers_total.labels("true").inc()
    metrics.approvals_total.labels("approve").inc()
    metrics.pii_redactions_total.labels("email").inc()

    text = metrics.render()[0].decode()
    assert "agentforge_chat_requests_total" in text
    assert 'agentforge_answers_total{grounded="true"}' in text
    assert 'agentforge_approvals_total{decision="approve"}' in text
    assert 'agentforge_pii_redactions_total{label="email"}' in text
