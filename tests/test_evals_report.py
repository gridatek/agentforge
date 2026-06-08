"""Eval report writer (run_evals) + reader (/evals). No graph/LLM involved."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from agentforge.api.main import app

EVALS_DIR = Path(__file__).resolve().parents[1] / "evals"


def test_write_report_roundtrip(tmp_path):
    sys.path.insert(0, str(EVALS_DIR))
    import run_evals  # noqa: E402  (added to path above)

    out = tmp_path / "results.json"
    results = [
        {"id": "q1", "question": "when is EDD required?", "passed": True, "detail": "ok"},
        {"id": "q2", "question": "capital of France?", "passed": False, "detail": "did not refuse"},
    ]
    run_evals._write_report(out, threshold=0.8, results=results)

    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["passed"] == 1
    assert report["total"] == 2
    assert report["pass_rate"] == 0.5
    assert report["threshold"] == 0.8
    assert len(report["cases"]) == 2
    assert "generated_at" in report


def test_evals_endpoint_null_when_absent(monkeypatch):
    # Point the API at a path that doesn't exist -> 200 with null body.
    from agentforge.api import evals as evals_module

    monkeypatch.setattr(
        evals_module.get_settings(), "evals_results_path", "/nonexistent/results.json"
    )
    resp = TestClient(app).get("/evals")
    assert resp.status_code == 200
    assert resp.json() is None


def test_evals_endpoint_serves_report(monkeypatch, tmp_path):
    report = {
        "generated_at": "2026-06-08T00:00:00+00:00",
        "threshold": 0.8,
        "passed": 9,
        "total": 10,
        "pass_rate": 0.9,
        "cases": [{"id": "q1", "question": "x", "passed": True, "detail": "ok"}],
    }
    path = tmp_path / "results.json"
    path.write_text(json.dumps(report), encoding="utf-8")

    from agentforge.api import evals as evals_module

    monkeypatch.setattr(evals_module.get_settings(), "evals_results_path", str(path))
    body = TestClient(app).get("/evals").json()
    assert body["pass_rate"] == 0.9
    assert body["cases"][0]["id"] == "q1"
