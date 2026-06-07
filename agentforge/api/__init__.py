"""FastAPI gateway exposing the agent over REST + SSE."""

from agentforge.api.main import app

__all__ = ["app"]
