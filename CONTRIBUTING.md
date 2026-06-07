# Contributing to AgentForge

Thanks for your interest! AgentForge is **pre-alpha** — the scaffold for all
phases is in place and we're iterating toward the v0.1 MVP. Issues labelled
`good first issue` track the post-MVP milestones in the README roadmap.

## Local setup

```bash
python -m venv .venv && . .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env                              # add your provider key

# Bring up Postgres + pgvector (and the rest of the stack)
docker compose up -d db
python -m agentforge.rag.ingest examples/banking-compliance/corpus

agentforge ask "What documents are needed for KYC verification?"
agentforge serve                                  # API on :8000
```

The Angular console lives in `apps/console` (see its README).

## Project layout

| Path | What |
|------|------|
| `agentforge/llm` | Provider-agnostic chat + embeddings layer |
| `agentforge/rag` | Ingestion, chunking, pgvector store, retrieval |
| `agentforge/agents` | LangGraph graph, nodes, state, tools, HITL |
| `agentforge/guardrails` | PII redaction, tool scoping |
| `agentforge/observability` | LangSmith / Langfuse adapters |
| `agentforge/api` | FastAPI gateway |
| `evals/` | Eval dataset + CI gate |
| `apps/console/` | Angular admin console |
| `examples/banking-compliance/` | Reference example + sample corpus |

## Before you open a PR

```bash
ruff check agentforge      # lint
pytest tests/ -q           # unit tests (no keys needed)
```

If your change touches retrieval or prompting, run the eval gate against a live
stack: `python evals/run_evals.py`.

## Conventions

- Keep the **LLM layer** the only place that talks to a model provider directly.
- New tools that have side effects must be added to `SENSITIVE_TOOLS` (or carry
  their own approval policy) — never auto-execute irreversible actions.
- Match the surrounding code style; `ruff` enforces formatting and imports.

By contributing you agree your work is licensed under Apache-2.0.
