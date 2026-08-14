FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app

ENV UV_HTTP_TIMEOUT=120
ENV UV_HTTP_RETRIES=5

COPY pyproject.toml /app/pyproject.toml
COPY uv.lock /app/uv.lock
COPY packages/contracts /app/packages/contracts
COPY services/api/pyproject.toml /app/services/api/pyproject.toml
COPY services/worker/pyproject.toml /app/services/worker/pyproject.toml

RUN apt-get update \
    && apt-get install --no-install-recommends -y tesseract-ocr tesseract-ocr-chi-sim \
    && rm -rf /var/lib/apt/lists/*

RUN uv sync --frozen --no-dev --no-install-workspace

COPY services/worker/app /app/services/worker/app
# The worker owns execution entry points, while radar and webhook domain
# services stay in the API package.  `app.__path__` joins these at runtime.
COPY services/api/app /app/services/api/app

RUN uv sync --frozen --no-dev --package docpilot-worker

WORKDIR /app/services/worker

ENV PYTHONPATH=/app/packages

CMD ["/app/.venv/bin/celery", "-A", "app.celery_app", "worker", "--loglevel=info"]
