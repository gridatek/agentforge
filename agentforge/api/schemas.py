"""Request/response models for the API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str
    # Conversation/checkpoint id. Omit to start a new thread.
    thread_id: str | None = None


class PendingAction(BaseModel):
    id: str | None = None
    name: str
    args: dict[str, Any] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    thread_id: str
    answer: str | None = None
    citations: list[dict[str, Any]] = Field(default_factory=list)
    pii_found: list[str] = Field(default_factory=list)
    # When the agent proposed a sensitive action, the run pauses here.
    approval_required: bool = False
    pending_action: PendingAction | None = None


class ApprovalRequest(BaseModel):
    thread_id: str
    decision: str = Field(description="'approve' or 'reject'")
