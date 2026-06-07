"""Tool scoping.

Decides which tool calls may run automatically and which must be gated behind
human approval. The policy is data-driven (``settings.sensitive_tools``) so it's
auditable and easy to extend per deployment.
"""

from __future__ import annotations

from agentforge.config import get_settings


def requires_approval(tool_name: str) -> bool:
    """True if ``tool_name`` is sensitive and needs human-in-the-loop sign-off."""
    return tool_name in set(get_settings().sensitive_tools)


def is_allowed(tool_name: str, allowlist: set[str]) -> bool:
    """Enforce a per-agent allowlist — unknown tools are denied by default."""
    return tool_name in allowlist
