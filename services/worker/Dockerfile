FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app

ENV UV_HTTP_TIMEOUT=120
ENV UV_HTTP_RETRIES=5

COPY pyproject.toml /app/pyproject.toml
COPY uv.lock /app/uv.lock
COPY packages/contracts /app/packages/contracts
COPY services/api/pyproject.toml /app/services/api/pyproject.toml
COPY services/worker/pyproject.toml /app/services/worker/pyproject.toml

RUN uv sync --frozen --no-dev --no-install-workspace

COPY services/worker/app /app/services/worker/app

RUN uv sync --frozen --no-dev --package docpilot-worker

WORKDIR /app/services/worker

ENV PYTHONPATH=/app/packages

CMD ["/app/.venv/bin/celery", "-A", "app.celery_app", "worker", "--loglevel=info"]
