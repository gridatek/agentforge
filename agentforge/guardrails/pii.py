"""PII redaction.

A deliberately small, dependency-free redactor for the high-risk identifiers a
compliance assistant must never leak into prompts, traces, or tool calls.
Swap in Presidio or an LLM-based detector behind ``redact_pii`` without touching
callers. We intentionally do **not** redact names — they're needed for retrieval.
"""

from __future__ import annotations

import re

# (label, compiled pattern, replacement token)
_PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    ("email", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"), "[REDACTED_EMAIL]"),
    ("credit_card", re.compile(r"\b(?:\d[ -]*?){13,16}\b"), "[REDACTED_CARD]"),
    ("us_ssn", re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[REDACTED_SSN]"),
    ("iban", re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b"), "[REDACTED_IBAN]"),
    ("phone", re.compile(r"\b(?:\+?\d{1,3}[ -]?)?(?:\(?\d{2,4}\)?[ -]?){2,4}\d{2,4}\b"),
     "[REDACTED_PHONE]"),
]


def redact_pii(text: str) -> tuple[str, list[str]]:
    """Return ``(redacted_text, labels_found)``.

    ``credit_card`` runs before ``phone`` so long digit runs are classified as
    cards rather than phone numbers.
    """
    found: list[str] = []
    redacted = text
    for label, pattern, token in _PATTERNS:
        if pattern.search(redacted):
            found.append(label)
            redacted = pattern.sub(token, redacted)
    return redacted, found
