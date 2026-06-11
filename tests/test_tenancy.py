"""Tenant resolution + per-tenant isolation of the approval queue.

These cover the step-1 seam: identity from the X-Tenant-ID header, the safe
default-tenant fallback, id validation that forbids the composite delimiter,
and the guarantee that one tenant never sees another's pending approvals.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import agentforge.api.tenancy as tenancy
from agentforge.api import approvals
from agentforge.api.main import app
from agentforge.api.schemas import PendingAction


class _Req:
    """Minimal stand-in for a Starlette Request (only .headers.get is used)."""

    def __init__(self, headers: dict | None = None):
        self.headers = headers or {}


def test_missing_header_falls_back_to_default_tenant():
    from agentforge.config import get_settings

    assert tenancy.resolve_tenant(_Req()) == get_settings().default_tenant


def test_explicit_tenant_from_header():
    assert tenancy.resolve_tenant(_Req({"X-Tenant-ID": "acme"})) == "acme"


def test_invalid_tenant_id_rejected():
    with pytest.raises(HTTPException) as exc:
        tenancy.resolve_tenant(_Req({"X-Tenant-ID": "bad:id"}))
    assert exc.value.status_code == 400


def test_require_tenant_rejects_missing_header(monkeypatch):
    monkeypatch.setattr(
        tenancy, "get_settings", lambda: SimpleNamespace(require_tenant=True, default_tenant="default")
    )
    with pytest.raises(HTTPException) as exc:
        tenancy.resolve_tenant(_Req())
    assert exc.value.status_code == 400


def test_validate_thread_id_forbids_colon():
    with pytest.raises(HTTPException):
        tenancy.validate_thread_id("acme:t-1")  # can't smuggle a scope boundary


def test_scoped_thread_separates_same_bare_id():
    assert tenancy.scoped_thread("acme", "t-1") != tenancy.scoped_thread("globex", "t-1")


def test_approval_queue_is_isolated_per_tenant():
    # Two tenants reuse the same bare thread_id; their actions must not bleed.
    approvals.register("acme", "shared", PendingAction(name="file_sar"), "q-acme")
    approvals.register("globex", "shared", PendingAction(name="escalate_case"), "q-globex")
    client = TestClient(app)

    acme = client.get("/approvals", headers={"X-Tenant-ID": "acme"}).json()
    globex = client.get("/approvals", headers={"X-Tenant-ID": "globex"}).json()

    acme_shared = [d for d in acme if d["thread_id"] == "shared"]
    globex_shared = [d for d in globex if d["thread_id"] == "shared"]
    assert {d["action"]["name"] for d in acme_shared} == {"file_sar"}
    assert {d["action"]["name"] for d in globex_shared} == {"escalate_case"}

    # Resolving under the wrong tenant must not drop the other's entry.
    approvals.resolve("acme", "shared")
    still = client.get("/approvals", headers={"X-Tenant-ID": "globex"}).json()
    assert any(d["thread_id"] == "shared" for d in still)
    approvals.resolve("globex", "shared")
