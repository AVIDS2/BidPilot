FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install --no-install-recommends -y tesseract-ocr tesseract-ocr-chi-sim \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml /app/pyproject.toml
COPY uv.lock /app/uv.lock
COPY packages/contracts /app/packages/contracts
COPY services/api/pyproject.toml /app/services/api/pyproject.toml
COPY services/worker/pyproject.toml /app/services/worker/pyproject.toml

RUN uv sync --frozen --no-dev --no-install-workspace

COPY services/api/app /app/services/api/app
COPY services/api/alembic.ini /app/services/api/alembic.ini
COPY services/api/alembic /app/services/api/alembic
COPY sample-data/bidpilot-demo /app/sample-data/bidpilot-demo
COPY docs/agent-skills /app/docs/agent-skills
COPY scripts/setup_langgraph_checkpoints.py /app/scripts/setup_langgraph_checkpoints.py
COPY scripts/production_readiness.py /app/scripts/production_readiness.py

RUN uv sync --frozen --no-dev --package docpilot-api

WORKDIR /app/services/api

ENV PYTHONPATH=/app/packages

EXPOSE 8000

CMD ["/app/.venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
