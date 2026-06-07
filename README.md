# AgentForge

> A self-hostable, full-stack platform for building production-grade agentic-RAG applications — LangGraph orchestration, RAG, pluggable observability, one-command deploy, and a real admin console.

<!-- working name — alternatives: RagForge, LakeAgent. Scope: @gridatek -->

[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-pre--alpha-orange.svg)]()

---

## Why this exists

The LangChain ecosystem is full of libraries and notebooks, but short on **opinionated, self-hostable starter platforms** that bundle the whole production stack — agent orchestration, RAG, observability, CI/CD, *and a usable management console* — into something you can fork and deploy on your own infra in one command.

AgentForge fills that gap. It is not "a chatbot demo." It is a forkable foundation for teams who need agentic AI on their own infrastructure, with the auditability, guardrails, and predictable failure behavior that regulated industries (banking, insurance, healthcare) actually require.

A **banking compliance assistant** ships as the reference example — RAG over policies, AML/KYC rules and product sheets, with human-in-the-loop approval before any sensitive action — but the platform itself is domain-agnostic.

## What's in the box

- **Provider-agnostic LLM layer** — Claude / OpenAI / local Ollama, swappable via config.
- **RAG pipeline** — ingestion, chunking, embeddings, retrieval with citations and grounded refusals.
- **Agentic orchestration** — stateful LangGraph agents with durable execution and human-in-the-loop approval nodes.
- **Guardrails** — PII redaction, tool scoping, and policy enforcement via LangChain middleware.
- **Pluggable observability** — LangSmith by default; Langfuse adapter for a fully self-hosted setup.
- **Evals as a CI gate** — regression tests on retrieval quality and answer faithfulness that block bad deploys.
- **Admin console** — Angular UI for chat, trace inspection, eval scores, and the approval queue.
- **One-command local run** — `docker compose up` to a working agent + console.

## Architecture (high level)

```
        ┌───────────────────────────┐
        │   Angular admin console   │  chat · traces · evals · approvals
        └─────────────┬─────────────┘
                      │ REST / SSE
        ┌─────────────┴─────────────┐
        │      FastAPI gateway      │
        └─────────────┬─────────────┘
                      │
      ┌───────────────┼───────────────┐
      ▼               ▼               ▼
 ┌──────────┐    ┌──────────┐  ┌───────────────┐
 │ LangGraph│    │   RAG    │  │ Observability │
 │  agents  │◄──►│ pipeline │  │   adapter     │
 │ (+ HITL) │    │(pgvector)│  │  LangSmith /  │
 └────┬─────┘    └──────────┘  │   Langfuse    │
      │                        └───────────────┘
 ┌────┴─────┐
 │ LLM layer│  Claude · OpenAI · Ollama
 └──────────┘
```

## Tech stack

| Layer            | Choice                                  | Notes                                      |
|------------------|------------------------------------------|--------------------------------------------|
| Language         | Python                                   | Backend + agents                           |
| Agent framework  | LangChain 1.0 / LangGraph 1.0            | Stable since Oct 2025, no breaking changes until 2.0 |
| API              | FastAPI                                  | REST + streaming                           |
| Vector store     | Postgres + pgvector                      | Self-hostable; Qdrant adapter planned      |
| Observability    | LangSmith (default) · Langfuse (OSS)     | Pluggable backend                          |
| Frontend         | Angular                                  | Management console                         |
| Packaging        | Docker / Docker Compose                  | One-command local run                      |
| CI/CD            | GitHub Actions                           | Eval-gated deploys                         |
| Production       | Kubernetes (or LangGraph Platform)       | Self-hosted or managed                     |

## Quickstart

Zero config — no API key required. A bundled Ollama serves the chat model and
embeddings, the models are pulled automatically, and the sample banking corpus
is ingested on first boot.

```bash
git clone https://github.com/gridatek/agentforge
cd agentforge
docker compose up
# → console at http://localhost:4200, API at http://localhost:8000
```

First boot pulls ~2.5 GB of local models. To use a cloud provider instead, drop
a `.env` (see `.env.example`) — e.g. `CHAT_MODEL=anthropic:claude-opus-4-8` +
`ANTHROPIC_API_KEY=…` — and those values override the local defaults.

## Repo structure

The scaffold for every phase is in place — a runnable skeleton you extend.

```
agentforge/
├── agentforge/              # Python package
│   ├── llm/                 # provider-agnostic chat + embeddings layer
│   ├── rag/                 # ingestion, chunking, pgvector store, retrieval
│   ├── agents/              # LangGraph graph, nodes, state, tools, HITL
│   ├── guardrails/          # PII redaction, tool scoping
│   ├── observability/       # LangSmith / Langfuse adapters
│   ├── api/                 # FastAPI gateway (chat + approvals, SSE)
│   ├── config.py            # env-driven settings
│   └── cli.py               # agentforge ingest | ask | serve
├── apps/
│   └── console/             # Angular admin UI
├── examples/
│   └── banking-compliance/  # reference example + sample corpus
├── evals/                   # eval dataset + CI gate
├── tests/                   # unit tests (no API keys needed)
├── db/init.sql              # enables pgvector
├── docker-compose.yml       # db + api + console
├── Dockerfile
├── .github/workflows/ci.yml # lint · unit tests · eval gate
├── pyproject.toml
├── CONTRIBUTING.md
└── README.md
```

---

## Roadmap

The phases double as a learning path for the AI Engineer / GenAI skill set (Python · LangGraph · LangChain · LLM · RAG · Prompt Engineering · LangSmith · Docker · CI/CD · production deployment). **v0.1 is the only thing that must ship before the platform is useful and demo-able** — everything after is iterative and "good first issue" friendly.

### Phase 0 — Scaffold
Project setup, provider-agnostic LLM layer (Claude / OpenAI / Ollama fallback), sample banking corpus, base Docker Compose.
*Skills: Python, LLM.*

### Phase 1 — RAG baseline + Prompt Engineering
Ingestion → chunking → embeddings → pgvector → grounded answers with citations and out-of-scope refusals. System prompts, structured output, few-shot patterns.
*Skills: RAG, Prompt Engineering, LLM.*

### Phase 2 — Agentic orchestration (LangGraph)
Single stateful graph: planner → retrieval/tool nodes → **human-in-the-loop approval** before sensitive actions. Durable execution that survives restarts. Guardrails middleware (PII redaction, tool scoping).
*Skills: LangGraph, LangChain, agents. **The core of the profile — invest the most time here.***

### Phase 3 — Observability & Evals
LangSmith tracing on every node from day one. Eval dataset (question / expected-answer), regression evals on retrieval quality + faithfulness, prompt versioning.
*Skills: observability (LangSmith). **The differentiator most candidates skip.***

### ⭐ **v0.1 MVP = Phases 0–3, end-to-end, `docker compose up`**
RAG + one LangGraph agent + HITL + tracing + minimal console. This is already a star-worthy repo and a complete "I shipped this stack" story. **Ship this before going deep on the rest.**

---

### Phase 4 — Production: Docker + CI/CD + deploy
Full containerization, GitHub Actions pipeline running the eval suite as a **gate** (fail the build if faithfulness drops). Deploy to Kubernetes / IBM Cloud, or compare against LangGraph Platform one-click deploy. Monitoring + alerting.
*Skills: Docker, CI/CD, production deployment. **Home turf — lean on existing skills.***

### Phase 5 — Management console (Angular)
Chat UI + admin views: live traces, eval scores, approval queue. The full-stack surface almost no LangChain-demo author ships — the standout.
*Skills: full-stack differentiator.*

### Beyond v1.0 — community milestones
- Langfuse adapter (fully self-hosted observability)
- Multi-agent / supervisor graphs
- Qdrant + alternative vector-store adapters
- Multi-tenancy
- Additional reference examples (insurance, support)

---

## Roadmap at a glance

| Version | Contents                                  | Goal                          |
|---------|-------------------------------------------|-------------------------------|
| v0.1    | Phases 0–3 (RAG + agent + HITL + tracing) | Demo-able, forkable MVP       |
| v0.2    | Phase 4 (Docker + eval-gated CI/CD)       | Production-deployable         |
| v0.3    | Phase 5 (Angular console)                 | Full-stack platform           |
| v1.0    | Hardening, docs, second example           | Stable public release         |

## Contributing

Contributions welcome once v0.1 lands. See `CONTRIBUTING.md`. Issues labelled `good first issue` track the post-MVP milestones above.

## License

Apache-2.0.