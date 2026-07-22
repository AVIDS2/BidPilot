#!/usr/bin/env bash
set -euo pipefail

APP_ROOT=/app/bidpilot
REPO_ROOT="$APP_ROOT/repo"
COMPOSE_FILE="$APP_ROOT/docker-compose.yml"
NEXT_COMPOSE_FILE="$APP_ROOT/.docker-compose.next.yml"

cd "$REPO_ROOT"
git pull --ff-only origin master

# Keep deployment topology outside Git while making the Compose template itself
# versioned with application code. The server .env is never copied or modified.
cp docker-compose.production.yml "$NEXT_COMPOSE_FILE"
trap 'rm -f "$NEXT_COMPOSE_FILE"' EXIT

cd "$APP_ROOT"
docker compose -f "$NEXT_COMPOSE_FILE" --env-file .env config --quiet
mv "$NEXT_COMPOSE_FILE" "$COMPOSE_FILE"
trap - EXIT
docker compose up -d --build
