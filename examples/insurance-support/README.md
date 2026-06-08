# Insurance-support example

The same AgentForge platform retargeted from banking compliance to **auto-insurance
support** — only the corpus, system prompt, and config change; no code changes.

- **Corpus** (`corpus/`): policy coverage summary, claims process, and fraud /
  escalation guidance for a fictional "AutoGuard" auto policy.
- **Persona**: set via `SYSTEM_PROMPT` (see `config.yaml`) — an insurance support
  assistant that answers only from the policy docs and escalates suspected fraud.
- **Sensitive action**: reuses the generic `escalate_case` tool (escalate a claim
  to a human adjuster), gated by human approval. Domain-specific tools would be
  added in `agentforge/agents/tools.py`.

## Run it

```bash
docker compose -f docker-compose.yml -f docker-compose.insurance.yml up
```

This ingests the insurance corpus into a separate `insurance_support` collection
(so it coexists with the banking data) and points the assistant at it. Then ask,
e.g., "What is the collision deductible?" or "How long do I have to report a
claim?".

## Evals

`evals.jsonl` holds regression cases for this corpus (coverage facts, claims
timelines, fraud escalation, and out-of-scope refusals). Against a running stack
that has ingested this corpus:

```bash
python evals/run_evals.py --dataset examples/insurance-support/evals.jsonl
```
