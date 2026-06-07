"""Unit tests for guardrails — no external services required, so CI can run
these on every push without API keys or a database."""

from agentforge.guardrails.pii import redact_pii


def test_redacts_email():
    redacted, found = redact_pii("Contact me at jane.doe@example.com please")
    assert "jane.doe@example.com" not in redacted
    assert "[REDACTED_EMAIL]" in redacted
    assert "email" in found


def test_redacts_ssn():
    redacted, found = redact_pii("SSN is 123-45-6789")
    assert "123-45-6789" not in redacted
    assert "us_ssn" in found


def test_clean_text_unchanged():
    text = "What documents are needed for KYC verification?"
    redacted, found = redact_pii(text)
    assert redacted == text
    assert found == []
