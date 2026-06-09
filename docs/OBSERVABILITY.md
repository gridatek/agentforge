# Observability

Every graph node and LLM call can be traced. One switch — `OBSERVABILITY_BACKEND`
— selects where traces go. Callbacks are attached to each run in the API
(`_run_config`), so tracing is uniform across `/chat`, `/chat/stream`, and
`/approve`.

| `OBSERVABILITY_BACKEND` | Where traces go | Extra install |
|---|---|---|
| `none` (default) | nowhere (local dev / tests) | — |
| `langsmith` | LangSmith (hosted) | — |
| `langfuse` | Langfuse (cloud **or** self-hosted) | `agentforge[langfuse]` |

For runtime metrics (request rates, grounded-answer ratio, approvals, …) see the
Prometheus `/metrics` endpoint and the console's Operations tab instead — that's
complementary to the per-trace view here.

## LangSmith

```env
OBSERVABILITY_BACKEND=langsmith
LANGCHAIN_API_KEY=ls-...
LANGCHAIN_PROJECT=agentforge
```

`setup_observability()` exports the `LANGCHAIN_*` env at startup and LangChain
auto-traces every node — no per-call wiring.

## Langfuse — cloud

Create a project at https://cloud.langfuse.com, then:

```env
OBSERVABILITY_BACKEND=langfuse
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://cloud.langfuse.com
```

The API image must include the extra. Locally that's `pip install
'agentforge[langfuse]'`; in containers, build with `--build-arg EXTRAS=langfuse`
(the self-host overlay below does this for you).

## Langfuse — fully self-hosted

[`docker-compose.langfuse.yml`](../docker-compose.langfuse.yml) adds a Langfuse
server and its own Postgres, and points the API at it. Bring up the stack with
the overlay:

```bash
docker compose -f docker-compose.yml -f docker-compose.langfuse.yml up --build
```

`--build` rebuilds the api image with the `langfuse` extra the first time. Then:

1. Open <http://localhost:3000>, create an account + a project.
2. Copy the project's keys into `.env`:
   ```env
   LANGFUSE_PUBLIC_KEY=pk-lf-...
   LANGFUSE_SECRET_KEY=sk-lf-...
   ```
3. Restart the api: `docker compose ... up -d api`.
4. Ask a question, then refresh the Langfuse project — a trace per graph node
   (guardrails → supervisor → retrieve → answer → …) appears.

`LANGFUSE_HOST` is already set to `http://langfuse:3000` by the overlay. Set
`LANGFUSE_NEXTAUTH_SECRET` and `LANGFUSE_SALT` in `.env` for anything beyond a
local trial.

> Uses Langfuse v2 (single container + Postgres) to keep self-hosting light; the
> `langfuse` extra is pinned to match. Langfuse v3 self-hosting (ClickHouse +
> Redis + object storage) is out of scope for this overlay — point `LANGFUSE_HOST`
> at such an instance and bump the extra if you run one.

## Kubernetes

The manifests don't bundle Langfuse. Run it (or LangSmith) out of band and set
`OBSERVABILITY_BACKEND` + the `LANGFUSE_*` / `LANGCHAIN_*` keys in the Secret;
for Langfuse, build/push an api image with `EXTRAS=langfuse`.
