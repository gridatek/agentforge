"""AgentForge command-line entrypoint.

    agentforge ingest [CORPUS_DIR]   # load a corpus into the vector store
    agentforge ask "QUESTION"        # one-shot query against the agent
    agentforge backfill-tenant       # stamp untagged chunks with the default tenant
    agentforge serve                 # run the FastAPI gateway
"""

from __future__ import annotations

import argparse
import uuid


def _tenant(args: argparse.Namespace) -> str:
    from agentforge.config import get_settings

    return args.tenant or get_settings().default_tenant


def _cmd_ingest(args: argparse.Namespace) -> None:
    from agentforge.rag.ingest import ingest

    tenant = _tenant(args)
    count = ingest(args.corpus_dir, tenant)
    print(f"Ingested {count} chunks from {args.corpus_dir} for tenant {tenant!r}")


def _cmd_backfill_tenant(args: argparse.Namespace) -> None:
    from agentforge.rag.store import backfill_tenant

    tenant = _tenant(args)
    count = backfill_tenant(tenant)
    print(f"Backfilled {count} untagged chunks to tenant {tenant!r}")


def _cmd_ask(args: argparse.Namespace) -> None:
    from agentforge.agents import get_compiled_graph

    config = {"configurable": {"thread_id": str(uuid.uuid4())}}
    invoke_input = {"question": args.question, "tenant_id": _tenant(args)}
    result = get_compiled_graph().invoke(invoke_input, config=config)
    if result.get("__interrupt__"):
        print("[approval required]", result["__interrupt__"][0].value)
    else:
        print(result.get("answer", ""))
        for c in result.get("citations", []):
            section = f" › {c['section']}" if c.get("section") else ""
            print(f"  - {c['source']}{section} (relevance={c['score']})")


def _cmd_serve(args: argparse.Namespace) -> None:
    import uvicorn

    from agentforge.config import get_settings

    settings = get_settings()
    uvicorn.run("agentforge.api:app", host=settings.api_host, port=settings.api_port)


def main() -> None:
    parser = argparse.ArgumentParser(prog="agentforge")
    sub = parser.add_subparsers(dest="command", required=True)

    p_ingest = sub.add_parser("ingest", help="Load a corpus into the vector store")
    p_ingest.add_argument(
        "corpus_dir", nargs="?", default="examples/banking-compliance/corpus"
    )
    p_ingest.add_argument("--tenant", help="Tag chunks for this tenant (default: DEFAULT_TENANT)")
    p_ingest.set_defaults(func=_cmd_ingest)

    p_backfill = sub.add_parser(
        "backfill-tenant", help="Stamp untagged chunks with the default (or given) tenant"
    )
    p_backfill.add_argument("--tenant", help="Tenant id to stamp (default: DEFAULT_TENANT)")
    p_backfill.set_defaults(func=_cmd_backfill_tenant)

    p_ask = sub.add_parser("ask", help="One-shot query against the agent")
    p_ask.add_argument("question")
    p_ask.add_argument("--tenant", help="Scope retrieval to this tenant (default: DEFAULT_TENANT)")
    p_ask.set_defaults(func=_cmd_ask)

    p_serve = sub.add_parser("serve", help="Run the FastAPI gateway")
    p_serve.set_defaults(func=_cmd_serve)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
