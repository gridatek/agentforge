"""Knowledge-base catalog + /documents endpoint. No DB available in unit CI, so
this exercises the graceful-empty path (store unreachable -> [])."""

from __future__ import annotations

from fastapi.testclient import TestClient

from agentforge.api.main import app
from agentforge.rag.catalog import list_documents


def test_list_documents_empty_when_store_unreachable():
    # No Postgres in the unit-test job — must degrade to an empty catalog,
    # never raise.
    assert list_documents() == []


def test_documents_endpoint_returns_list():
    resp = TestClient(app).get("/documents")
    assert resp.status_code == 200
    assert resp.json() == []
