"""Checkpointer selection + conninfo handling. No DB connection is opened."""

from __future__ import annotations

from agentforge.agents.checkpoint import _conninfo


def test_conninfo_strips_sqlalchemy_driver():
    url = "postgresql+psycopg://user:pass@host:5432/agentforge"
    assert _conninfo(url) == "postgresql://user:pass@host:5432/agentforge"


def test_conninfo_only_rewrites_scheme():
    # A password that happens to contain the scheme text must be left intact.
    url = "postgresql+psycopg://u:postgresql+psycopg@host/db"
    assert _conninfo(url) == "postgresql://u:postgresql+psycopg@host/db"


def test_default_checkpoint_backend_is_memory():
    from agentforge.config import Settings

    assert Settings().checkpoint_backend == "memory"
