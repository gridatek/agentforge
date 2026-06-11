"""Tenant identity + per-tenant scoping for graph threads and approvals.

The tenant is taken from the ``X-Tenant-ID`` header (trusted for now —
authentication arrives in a later step) and used to namespace checkpoint
threads and the approval registry, so one tenant can never see or resume
another's runs. The knowledge base is scoped separately (chunks are tagged with
tenant_id at ingest and retrieval is filtered to the caller's tenant); see
``agentforge.rag.store.tenant_filter``.
"""

from __future__ import annotations

import re

from fastapi import HTTPException, Request

from agentforge.config import get_settings

TENANT_HEADER = "X-Tenant-ID"
# Deliberately excludes ':' (the composite-key delimiter) so neither a tenant
# id nor a thread id can forge another tenant's scope.
_VALID_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def resolve_tenant(request: Request) -> str:
    """FastAPI dependency returning the validated tenant id for the request.

    Missing header -> ``default_tenant`` (unless ``require_tenant`` is set, in
    which case it's a 400). An ill-formed id is always a 400.
    """
    settings = get_settings()
    raw = request.headers.get(TENANT_HEADER)
    if not raw:
        if settings.require_tenant:
            raise HTTPException(status_code=400, detail=f"Missing {TENANT_HEADER} header")
        return settings.default_tenant
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
