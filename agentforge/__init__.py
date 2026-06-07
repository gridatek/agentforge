"""AgentForge — a self-hostable platform for agentic-RAG applications.

The package is organized to mirror the platform's phases:

- ``agentforge.llm``           provider-agnostic chat-model + embeddings layer
- ``agentforge.rag``           ingestion, chunking, embeddings, retrieval
- ``agentforge.guardrails``    PII redaction, tool scoping
- ``agentforge.observability`` LangSmith / Langfuse tracing adapters
- ``agentforge.agents``        LangGraph graph, nodes, state, HITL
- ``agentforge.api``           FastAPI gateway (chat + approvals)
"""

__version__ = "0.1.0.dev0"
