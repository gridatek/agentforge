"""In-process registry of sensitive actions paused awaiting human approval.

This mirrors the agent's checkpointer: it is process-local, which is fine because
the default ``MemorySaver`` is too — a paused thread can only be resumed by the
same process that holds its checkpoint. Both become shared/durable together when
you switch to ``PostgresSaver`` (see ``agents/graph.py``); until then run a single
API replica for HITL.

Entries are keyed by ``scoped_thread(tenant, thread)`` so two tenants reusing
the same bare ``thread_id`` stay isolated, and ``list_pending(tenant)`` only
ever returns the caller's own queue.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from agentforge.api.schemas import PendingAction
from agentforge.api.tenancy import scoped_thread
from agentforge.observability import metrics


@dataclass
class PendingApproval:
    tenant_id: str
    thread_id: str  # bare, client-facing id (the composite is the dict key)
    action: PendingAction
    question: str
    created_at: float


_pending: dict[str, PendingApproval] = {}  # key: scoped_thread(tenant, thread)
_lock = threading.Lock()


def register(tenant_id: str, thread_id: str, action: PendingAction, question: str) -> None:
    """Record (or refresh) a thread that paused for approval."""
    with _lock:
        _pending[scoped_thread(tenant_id, thread_id)] = PendingApproval(
            tenant_id=tenant_id,
            thread_id=thread_id,
            action=action,
            question=question,
            created_at=time.time(),
        )
        metrics.pending_approvals.set(len(_pending))


def resolve(tenant_id: str, thread_id: str) -> None:
    """Drop a thread once its approval has been decided."""
    with _lock:
        _pending.pop(scoped_thread(tenant_id, thread_id), None)
        metrics.pending_approvals.set(len(_pending))


def list_pending(tenant_id: str | None = None) -> list[PendingApproval]:
    """Pending approvals, oldest first; scoped to ``tenant_id`` when given."""
    with _lock:
        items = list(_pending.values())
    if tenant_id is not None:
        items = [p for p in items if p.tenant_id == tenant_id]
    return sorted(items, key=lambda p: p.created_at)
