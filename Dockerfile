# --- Build the AgentForge API image ---
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

LABEL org.opencontainers.image.source="https://github.com/gridatek/agentforge"
LABEL org.opencontainers.image.description="AgentForge API gateway"

WORKDIR /app

# Install dependencies first (cached layer). Optional extras can be baked in at
# build time, e.g. --build-arg EXTRAS=langfuse (used by docker-compose.langfuse.yml).
ARG EXTRAS=""
COPY pyproject.toml README.md ./
COPY agentforge ./agentforge
RUN pip install --upgrade pip && pip install ".${EXTRAS:+[${EXTRAS}]}"

# Bundle the reference corpus so the image is self-contained for ingest
# (compose bind-mounts ./examples over this; k8s/standalone runs rely on it).
COPY examples ./examples

# Run as an unprivileged user (own /app so volume mounts/ingest still work).
RUN useradd --create-home --uid 10001 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Default command runs the gateway; override for ingest/evals. Horizontal
# scaling is handled by orchestrator replicas, so the process stays single-worker
# (avoids each worker racing on startup auto-ingest).
CMD ["uvicorn", "agentforge.api:app", "--host", "0.0.0.0", "--port", "8000"]
