"""Agent tools.

Tools the compliance agent can call. Sensitive ones (listed in
``settings.sensitive_tools``) are routed through human approval before they run;
the functions here are the *execution* side, invoked only after sign-off.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langchain_core.tools import tool


@tool
def escalate_case(customer_ref: str, reason: str) -> str:
    """Escalate a customer case to a human compliance officer.

    Args:
        customer_ref: Internal reference for the customer/case.
        reason: Why escalation is warranted.
    """
    # In a real deployment this would open a ticket / notify a queue.
    return f"Case {customer_ref} escalated to compliance. Reason: {reason}"


@tool
def file_sar(customer_ref: str, summary: str) -> str:
    """File a Suspicious Activity Report (SAR) for a customer.

    Args:
        customer_ref: Internal reference for the customer/case.
        summary: Short summary of the suspicious activity.
    """
    return f"SAR drafted for {customer_ref}: {summary}"


# Registry the graph uses to bind tools to the model and to execute them.
TOOLS = [escalate_case, file_sar]
_TOOL_MAP: dict[str, Callable[..., str]] = {t.name: t for t in TOOLS}


def execute_tool(name: str, args: dict[str, Any]) -> str:
    """Run a tool by name. Raises KeyError for unknown tools (deny-by-default)."""
    return _TOOL_MAP[name].invoke(args)
