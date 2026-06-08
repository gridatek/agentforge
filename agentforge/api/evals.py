"""Read the eval report that ``evals/run_evals.py --out`` produces.

The API just serves the latest run; producing it is a CI/ops step (CI uploads it
as an artifact; locally you can run evals against the live stack). Absent or
malformed file -> ``None``, which the console renders as a "not run yet" state.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agentforge.config import get_settings


def load_report() -> dict[str, Any] | None:
    path = Path(get_settings().evals_results_path)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
