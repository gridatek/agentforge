# --- Build the AgentForge API image ---
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install dependencies first (cached layer).
COPY pyproject.toml README.md ./
COPY agentforge ./agentforge
RUN pip install --upgrade pip && pip install .

EXPOSE 8000

# Default command runs the gateway; override for ingest/evals.
CMD ["uvicorn", "agentforge.api:app", "--host", "0.0.0.0", "--port", "8000"]
