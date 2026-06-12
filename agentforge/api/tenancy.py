"""Tenant identity + per-tenant scoping for graph threads and approvals.

The tenant is derived from the request's verified identity (see
``agentforge.api.auth``): with a real ``AUTH_BACKEND`` the authenticated
credential carries the tenant; with ``AUTH_BACKEND=none`` the ``X-Tenant-ID``
header is trusted (dev / single-tenant). Either way the resolved tenant
namespaces checkpoint threads and the approval registry, so one tenant can
never see or resume another's runs. The knowledge base is scoped separately
(chunks are tagged with tenant_id at ingest and retrieval is filtered to the
caller's tenant); see ``agentforge.rag.store.tenant_filter``.
"""

from __future__ import annotations

import re

from fastapi import HTTPException, Request

from agentforge.api.auth import authenticate
from agentforge.config import get_settings

TENANT_HEADER = "X-Tenant-ID"
# Deliberately excludes ':' (the composite-key delimiter) so neither a tenant
# id nor a thread id can forge another tenant's scope.
_VALID_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def resolve_tenant(request: Request) -> str:
    """FastAPI dependency returning the validated tenant id for the request.

    When an auth backend is configured the tenant comes from the verified
    credential (the ``X-Tenant-ID`` header is ignored). With ``AUTH_BACKEND=none``
    the header is trusted: missing header -> ``default_tenant`` (unless
    ``require_tenant`` is set, in which case it's a 400). An ill-formed id is
    always a 400, regardless of where it came from.
    """
    principal = authenticate(request)
    if principal is not None:
        return _validate_tenant_id(principal.tenant_id)
    settings = get_settings()
    raw = request.headers.get(TENANT_HEADER)
    if not raw:
        if settings.require_tenant:
            raise HTTPException(status_code=400, detail=f"Missing {TENANT_HEADER} header")
        return settings.default_tenant
    return _validate_tenant_id(raw)


def _validate_tenant_id(raw: str) -> str:
    if not _VALID_ID.match(raw):
        raise HTTPException(status_code=400, detail="Invalid tenant id")
    return raw


def validate_thread_id(thread_id: str) -> str:
    """Reject client thread ids that could break out of their tenant scope."""
    if not _VALID_ID.match(thread_id):
        raise HTTPException(status_code=400, detail="Invalid thread_id")
    return thread_id


def scoped_thread(tenant_id: str, thread_id: str) -> str:
    """The internal checkpoint/registry key. Never exposed to the client."""
    return f"{tenant_id}:{thread_id}"
