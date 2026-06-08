"""In-process registry of sensitive actions paused awaiting human approval.

This mirrors the agent's checkpointer: it is process-local, which is fine because
the default ``MemorySaver`` is too — a paused thread can only be resumed by the
same process that holds its checkpoint. Both become shared/durable together when
you switch to ``PostgresSaver`` (see ``agents/graph.py``); until then run a single
API replica for HITL.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from agentforge.api.schemas import PendingAction
from agentforge.observability import metrics


@dataclass
class PendingApproval:
    thread_id: str
    action: PendingAction
    question: str
    created_at: float


_pending: dict[str, PendingApproval] = {}
_lock = threading.Lock()


def register(thread_id: str, action: PendingAction, question: str) -> None:
    """Record (or refresh) a thread that paused for approval."""
    with _lock:
        _pending[thread_id] = PendingApproval(
            thread_id=thread_id,
            action=action,
            question=question,
            created_at=time.time(),
        )
        metrics.pending_approvals.set(len(_pending))


def resolve(thread_id: str) -> None:
    """Drop a thread once its approval has been decided."""
    with _lock:
        _pending.pop(thread_id, None)
        metrics.pending_approvals.set(len(_pending))


def list_pending() -> list[PendingApproval]:
    """Pending approvals, oldest first."""
    with _lock:
        return sorted(_pending.values(), key=lambda p: p.created_at)
