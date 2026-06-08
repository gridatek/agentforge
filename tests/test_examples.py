"""Validate the reference examples are well-formed (corpus chunks; evals parse).
Pure file/text work — no DB, model, or API keys."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from agentforge.config import Settings
from agentforge.rag.chunking import split_documents
from agentforge.rag.ingest import load_corpus

REPO = Path(__file__).resolve().parents[1]
EXAMPLES = [REPO / "examples" / "banking-compliance", REPO / "examples" / "insurance-support"]


@pytest.mark.parametrize("example", EXAMPLES, ids=lambda p: p.name)
def test_corpus_chunks_with_source_metadata(example):
    docs = load_corpus(example / "corpus")
    assert docs, f"no corpus documents under {example}"

    chunks = split_documents(docs)
    assert chunks, "corpus produced no chunks"
    assert all(c.metadata.get("source") for c in chunks), "every chunk needs a source"


def test_insurance_eval_dataset_is_valid():
    sys.path.insert(0, str(REPO / "evals"))
    import run_evals

    cases = run_evals._load_dataset(REPO / "examples" / "insurance-support" / "evals.jsonl")
    assert len(cases) >= 5
    for case in cases:
        assert case["id"] and case["question"]
        # Each case states an expectation the grader can check.
        assert (
            case.get("expect_refusal")
            or case.get("expect_grounded")
            or case.get("expected_keywords")
        ), f"case {case['id']} has no checkable expectation"


def test_system_prompt_override_defaults_off():
    # The platform stays on its built-in persona unless an example sets SYSTEM_PROMPT.
    assert Settings().system_prompt is None
