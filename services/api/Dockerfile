FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app

COPY pyproject.toml /app/pyproject.toml
COPY uv.lock /app/uv.lock
COPY services/api/pyproject.toml /app/services/api/pyproject.toml
COPY services/worker/pyproject.toml /app/services/worker/pyproject.toml

RUN uv sync --frozen --no-dev --no-install-workspace

COPY services/api/app /app/services/api/app
COPY services/api/alembic.ini /app/services/api/alembic.ini
COPY services/api/alembic /app/services/api/alembic

RUN uv sync --frozen --no-dev --package docpilot-api

WORKDIR /app/services/api

EXPOSE 8000

CMD ["/app/.venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
