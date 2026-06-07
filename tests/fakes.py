"""Test doubles for exercising the agent graph without external services.

``FakeChatModel`` returns scripted responses (optionally with tool calls), so we
can drive every branch of the graph — grounded answers, refusals, and the HITL
approval path — with no API key and no network.
"""

from __future__ import annotations

from langchain_core.documents import Document
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from agentforge.rag.retriever import Citation, RetrievalResult


class FakeChatModel(BaseChatModel):
    """A chat model that replays a queue of pre-baked AI messages."""

    # Consumed front-to-back via pop(0); each invoke() yields the next message.
    responses: list

    @property
    def _llm_type(self) -> str:
        return "fake-chat"

    def bind_tools(self, tools, **kwargs):  # noqa: ANN001 - mirror BaseChatModel
        # Tool *binding* is a no-op here; tool *calls* are scripted into responses.
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:  # noqa: ANN001
        message = self.responses.pop(0) if self.responses else AIMessage(content="")
        return ChatResult(generations=[ChatGeneration(message=message)])


def grounded_retrieval(text: str = "Enhanced due diligence applies at $10,000.") -> RetrievalResult:
    """A retrieval result with one relevant chunk (drives a grounded answer)."""
    return RetrievalResult(
        documents=[Document(page_content=text, metadata={"source": "aml.md", "title": "AML"})],
        citations=[Citation(source="aml.md", title="AML", snippet=text, score=0.1)],
    )


def empty_retrieval() -> RetrievalResult:
    """No relevant chunks (drives a grounded refusal)."""
    return RetrievalResult()
