# v0.1 Smoke Test

A manual end-to-end check of the MVP. CI validates the code (lint, unit tests,
Angular build, compose config) but **never runs the full stack** — the Ollama
model pull, corpus auto-ingest, and live SSE/HITL paths have only ever been
exercised by hand. Run this on a real Docker host before trusting a release.

**Time:** ~10–15 min (first run pulls ~2.5 GB of models).
**Needs:** Docker + Compose v2, ~4 GB free RAM, ports 4200/8000/5432/11434 free.

---

## 1. Bring up the stack

```bash
git clone https://github.com/gridatek/agentforge && cd agentforge
docker compose up
```

Watch the logs for, in order:

- [ ] `db` becomes healthy (`pg_isready`).
- [ ] `ollama-pull` pulls `nomic-embed-text` then `llama3.2`, then **exits 0**.
- [ ] `api` starts and logs `Auto-ingested N chunks from examples/banking-compliance/corpus`
      (N should be > 0 on first boot; 0 on later boots — ingest is idempotent).
- [ ] `console` serves on `:4200`.

> If `api` logs `Auto-ingest skipped (store/model not ready)`, the model pull
> didn't finish first — check the `ollama-pull` exit status and retry.

---

## 2. API health + grounded answer

```bash
curl -s localhost:8000/health
# → {"status":"ok"}

curl -s localhost:8000/chat \
  -H 'content-type: application/json' \
  -d '{"message":"When is enhanced due diligence required?"}' | jq
```

- [ ] `answer` mentions **$10,000** and cites a source (e.g. `[1]`).
- [ ] `citations[]` is non-empty; each has `source`, `section`, and a `score` in [0,1].
- [ ] `approval_required` is `false`.
- [ ] Note the returned `thread_id` (reused below if you want continuity).

---

## 3. Grounded refusal (out of scope)

```bash
curl -s localhost:8000/chat \
  -H 'content-type: application/json' \
  -d '{"message":"What is the capital of France?"}' | jq
```

- [ ] `answer` declines / says it's out of scope.
- [ ] `citations[]` is empty (`grounded` was false).

---

## 4. PII redaction

```bash
curl -s localhost:8000/chat \
  -H 'content-type: application/json' \
  -d '{"message":"My email is jane@example.com — what docs do I need for KYC?"}' | jq
```

- [ ] `pii_found` includes `"email"`.
- [ ] The answer still addresses KYC (passport, proof of address) — redaction
      didn't break retrieval.

---

## 5. Human-in-the-loop approval (the headline feature)

Ask for a sensitive action — the run should **pause**:

```bash
TID=$(curl -s localhost:8000/chat -H 'content-type: application/json' \
  -d '{"message":"File a SAR for customer C-9 for possible structuring"}' \
  | tee /dev/stderr | jq -r .thread_id)
```

- [ ] Response has `approval_required: true` and `pending_action.name == "file_sar"`.

Reject it first:

```bash
curl -s localhost:8000/approve -H 'content-type: application/json' \
  -d "{\"thread_id\":\"$TID\",\"decision\":\"reject\"}" | jq
```

- [ ] `answer` says the action was **not approved** / not performed.

Then run a fresh one and approve:

```bash
TID=$(curl -s localhost:8000/chat -H 'content-type: application/json' \
  -d '{"message":"File a SAR for customer C-9 for possible structuring"}' \
  | jq -r .thread_id)
curl -s localhost:8000/approve -H 'content-type: application/json' \
  -d "{\"thread_id\":\"$TID\",\"decision\":\"approve\"}" | jq
```

- [ ] `answer` confirms the action ran (contains `SAR drafted`).

Durability (optional): pause on a SAR, run `docker compose restart api`, then
`/approve` that `thread_id`.

- [ ] The resume still works after the restart — checkpoints persist in Postgres
      (`CHECKPOINT_BACKEND=postgres`).

---

## 6. Streaming (SSE)

```bash
curl -N localhost:8000/chat/stream \
  -H 'content-type: application/json' \
  -d '{"message":"What interest rate does the Everyday Savings account pay?"}'
```

- [ ] You see a `thread` event, then incremental `token` events, then a `done`
      event whose JSON `data` carries `answer` (mentions **3.5**) + `citations`.

---

## 7. Console (browser)

Open <http://localhost:4200>.

- [ ] Ask "When is enhanced due diligence required?" — the answer **streams in**
      token-by-token (blinking cursor), then citations appear below.
- [ ] A PII-containing question shows the "PII redacted" notice.
- [ ] "File a SAR for C-9…" surfaces the **Approval required** card with the
      tool + args; **Approve** executes, **Reject** does not.
- [ ] That same pending action appears under the **Approvals** tab (question +
      tool + args); approving/rejecting it there clears it from the queue.
- [ ] Stop the API (`docker compose stop api`) and send a message — the UI shows
      an error rather than hanging.
- [ ] Click **Knowledge** — a table lists the ingested sources (AML/KYC policy,
      product sheet) with their chunk counts.
- [ ] Click **Operations** — tiles show live counts (chat requests, grounded %,
      approvals, PII redactions, HTTP requests) that update as you use Chat.

---

## 8. Metrics

```bash
curl -s localhost:8000/metrics | grep agentforge_
```

- [ ] After running the steps above, you see `agentforge_chat_requests_total`,
      `agentforge_answers_total{grounded=...}`, `agentforge_approvals_total{decision=...}`,
      `agentforge_pii_redactions_total{label="email"}`, and the
      `agentforge_http_*` series with non-zero values.

---

## 9. (Optional) Tracing

Set a backend in `.env` and restart:

```env
OBSERVABILITY_BACKEND=langsmith
LANGCHAIN_API_KEY=ls-...
```

- [ ] After a chat, traces for each graph node appear in the LangSmith project.

---

## Teardown

```bash
docker compose down          # keep volumes (pgdata, ollama models)
docker compose down -v       # also wipe the DB + pulled models
```

---

## If something fails

| Symptom | Likely cause |
|---|---|
| `api` exits / can't reach DB | `db` not healthy yet — Compose should gate this; check `depends_on`. |
| Auto-ingest skipped | `ollama-pull` didn't finish before `api` started. |
| Empty citations on every question | `MIN_RELEVANCE` too strict for the embedding model — lower it in `.env`. |
| Console can't reach API | The console proxies `/api` to `API_UPSTREAM` (default `api:8000`); check the `api` service is up and on the same network. |
| Slow / OOM on first boot | Model pull needs RAM+disk; give Docker more, or use a cloud provider via `.env`. |

Found a discrepancy? That's exactly what this checklist is for — open an issue
with the failing step and the relevant `docker compose logs`.
