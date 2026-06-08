# Reference examples

AgentForge is domain-agnostic — the platform is the agent; an example is just a
corpus + a system prompt + config. Each one below runs on the same code.

| Example | Domain | Run |
|---|---|---|
| [`banking-compliance`](banking-compliance/) | AML/KYC policy + product sheets, with HITL before filing a SAR / escalating a case | default (`docker compose up`) |
| [`insurance-support`](insurance-support/) | Auto-insurance policy, claims process, fraud escalation | `docker compose -f docker-compose.yml -f docker-compose.insurance.yml up` |

## Forking for your own domain

1. Drop your `.md` corpus under `examples/<name>/corpus/`.
2. Point ingestion at it (`AUTO_INGEST_CORPUS`) and pick a `COLLECTION_NAME`.
3. Set `SYSTEM_PROMPT` to frame the assistant for your domain (keep the
   "answer only from context, cite, refuse when out of scope" rules).
4. Optionally add domain-specific tools in `agentforge/agents/tools.py` and list
   the sensitive ones in `SENSITIVE_TOOLS` so they require human approval.
5. Add an `evals.jsonl` and gate on it in CI.

The insurance example is the smallest possible diff that does all of the above —
copy its `config.yaml` and compose overlay as a template.
