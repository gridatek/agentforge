"""Regression evals — the CI gate.

Scores two things the platform must not regress on:

1. **Retrieval grounding** — did we ground (or correctly refuse) as expected?
2. **Answer faithfulness** — for grounded questions, does the answer contain the
   expected facts; for out-of-scope questions, does the agent refuse?

Exits non-zero when the pass rate falls below ``--threshold`` so a bad change
fails the build. Run it against a live stack (DB ingested, model reachable):

    python -m agentforge.rag.ingest examples/banking-compliance/corpus
    python evals/run_evals.py --threshold 0.8
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

REFUSAL_MARKERS = ("don't know", "do not know", "out of scope", "cannot", "no relevant")


def _write_report(path: Path, threshold: float, results: list[dict]) -> None:
    """Persist a structured run so the console's Eval view can read it."""
    passed = sum(r["passed"] for r in results)
    total = len(results)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "threshold": threshold,
        "passed": passed,
        "total": total,
        "pass_rate": passed / total if total else 0.0,
        "cases": results,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")


def _load_dataset(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _looks_like_refusal(answer: str) -> bool:
    lowered = answer.lower()
    return any(marker in lowered for marker in REFUSAL_MARKERS)


def _evaluate_case(graph, case: dict) -> tuple[bool, str]:
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}
    result = graph.invoke({"question": case["question"]}, config=config)
    answer = (result.get("answer") or "").lower()
    grounded = bool(result.get("grounded"))

    if case.get("expect_refusal"):
        ok = not grounded and _looks_like_refusal(answer)
        return ok, "refused" if ok else "did NOT refuse out-of-scope question"

    if case.get("expect_grounded") and not grounded:
        return False, "expected grounded retrieval, got none"

    missing = [kw for kw in case.get("expected_keywords", []) if kw.lower() not in answer]
    if missing:
        return False, f"missing expected facts: {missing}"
    return True, "ok"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run AgentForge regression evals")
    parser.add_argument("--dataset", default=str(Path(__file__).parent / "dataset.jsonl"))
    parser.add_argument("--threshold", type=float, default=0.8)
    parser.add_argument("--out", help="Write a JSON report here (for the console Eval view).")
    args = parser.parse_args()

    from agentforge.agents import get_compiled_graph

    graph = get_compiled_graph()
    cases = _load_dataset(Path(args.dataset))

    results: list[dict] = []
    for case in cases:
        ok, detail = _evaluate_case(graph, case)
        results.append(
            {"id": case["id"], "question": case["question"], "passed": ok, "detail": detail}
        )
        print(f"[{'PASS' if ok else 'FAIL'}] {case['id']}: {detail}")

    passed = sum(r["passed"] for r in results)
    rate = passed / len(cases) if cases else 0.0
    print(f"\nPass rate: {passed}/{len(cases)} = {rate:.0%} (threshold {args.threshold:.0%})")

    if args.out:
        _write_report(Path(args.out), args.threshold, results)
        print(f"Wrote report to {args.out}")

    return 0 if rate >= args.threshold else 1


if __name__ == "__main__":
    sys.exit(main())
