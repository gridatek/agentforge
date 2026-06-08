"""Durable LangGraph checkpointer backed by Postgres.

Used when ``CHECKPOINT_BACKEND=postgres``. A persistent checkpointer makes
human-in-the-loop pauses survive process restarts and resume correctly no matter
which replica handles ``/approve`` (the in-memory ``MemorySaver`` could not).
"""

from __future__ import annotations

from functools import lru_cache

from agentforge.config import get_settings


def _conninfo(database_url: str) -> str:
    """Turn a SQLAlchemy URL into a libpq conninfo string.

    The app uses ``postgresql+psycopg://…`` for langchain/SQLAlchemy; psycopg's
    pool wants a plain ``postgresql://…``.
    """
    return database_url.replace("postgresql+psycopg://", "postgresql://", 1)


@lru_cache
def get_postgres_checkpointer():
    """Process-wide PostgresSaver over a connection pool (tables created once)."""
    from langgraph.checkpoint.postgres import PostgresSaver
    from psycopg.rows import dict_row
    from psycopg_pool import ConnectionPool

    pool = ConnectionPool(
        conninfo=_conninfo(get_settings().database_url),
        max_size=20,
        # PostgresSaver requires autocommit; unprepared statements avoid clashes
        # with PgBouncer-style poolers.
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
        open=True,
    )
    checkpointer = PostgresSaver(pool)
    checkpointer.setup()
    return checkpointer
