"""Pending-approval registry + /approvals endpoint. No LLM/services needed."""

from __future__ import annotations

from fastapi.testclient import TestClient

from agentforge.api import approvals
from agentforge.api.main import app
from agentforge.api.schemas import PendingAction


def test_registry_register_list_resolve():
    approvals.register("t-1", PendingAction(name="file_sar", args={"customer": "C-9"}), "file a SAR")
    pending = approvals.list_pending()
    hit = next(p for p in pending if p.thread_id == "t-1")
    assert hit.action.name == "file_sar"
    assert hit.action.args == {"customer": "C-9"}

    approvals.resolve("t-1")
    assert all(p.thread_id != "t-1" for p in approvals.list_pending())


def test_approvals_endpoint_serializes():
    approvals.register("t-2", PendingAction(name="escalate_case", args={}), "escalate this")
    client = TestClient(app)

    item = next(d for d in client.get("/approvals").json() if d["thread_id"] == "t-2")
    assert item["action"]["name"] == "escalate_case"
    assert item["question"] == "escalate this"
    assert isinstance(item["created_at"], (int, float))

    approvals.resolve("t-2")
    assert all(d["thread_id"] != "t-2" for d in client.get("/approvals").json())
