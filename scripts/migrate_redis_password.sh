#!/usr/bin/env bash
# Safe Redis password migration for BidPilot live VPS.
# - Keeps existing redis volume/network/container names
# - Updates only DOCPILOT_REDIS_* in /app/bidpilot/.env
# - Recreates redis with requirepass, then restarts api/worker
# - Does NOT switch full production compose (postgres topology stays)
set -euo pipefail

APP_ROOT=/app/bidpilot
ENV_FILE="$APP_ROOT/.env"
COMPOSE_FILE="$APP_ROOT/docker-compose.yml"
cd "$APP_ROOT"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "missing $ENV_FILE" >&2
  exit 1
fi

# Generate password if not already set.
python3 - <<'PY'
from pathlib import Path
import secrets
import re
from urllib.parse import quote, urlparse, urlunparse

env_path = Path("/app/bidpilot/.env")
text = env_path.read_text(encoding="utf-8", errors="replace")
vals = {}
lines = text.splitlines()
for line in lines:
    if not line or line.strip().startswith("#") or "=" not in line:
        continue
    k, v = line.split("=", 1)
    vals[k.strip()] = v.strip().strip('"').strip("'")

existing = vals.get("DOCPILOT_REDIS_PASSWORD") or ""
redis_url = vals.get("DOCPILOT_REDIS_URL") or "redis://redis:6379/0"
parsed = urlparse(redis_url)
if existing:
    password = existing
else:
    password = secrets.token_urlsafe(24)

# Build redis URL with password, preserve host/port/db.
host = parsed.hostname or "redis"
port = parsed.port or 6379
db = (parsed.path or "/0")
user_password = quote(password, safe="")
new_url = f"redis://:{user_password}@{host}:{port}{db}"

out_lines = []
seen = set()
for line in lines:
    if not line or line.strip().startswith("#") or "=" not in line:
        out_lines.append(line)
        continue
    k, _ = line.split("=", 1)
    key = k.strip()
    if key == "DOCPILOT_REDIS_PASSWORD":
        out_lines.append(f"DOCPILOT_REDIS_PASSWORD={password}")
        seen.add(key)
    elif key == "DOCPILOT_REDIS_URL":
        out_lines.append(f"DOCPILOT_REDIS_URL={new_url}")
        seen.add(key)
    else:
        out_lines.append(line)

if "DOCPILOT_REDIS_PASSWORD" not in seen:
    out_lines.append(f"DOCPILOT_REDIS_PASSWORD={password}")
if "DOCPILOT_REDIS_URL" not in seen:
    out_lines.append(f"DOCPILOT_REDIS_URL={new_url}")

env_path.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
print("redis_password_ready", 1 if password else 0)
print("redis_host", host)
print("redis_port", port)
print("redis_db", db)
PY

# Patch live compose redis service to require password without full production topology swap.
python3 - <<'PY'
from pathlib import Path
import re

compose = Path("/app/bidpilot/docker-compose.yml")
text = compose.read_text(encoding="utf-8")
# Replace simple redis service block if still passwordless.
old = '''  redis:
    image: redis:7.4-alpine
    container_name: bidpilot-redis
    restart: unless-stopped
    ports:
      - "127.0.0.1:6379:6379"
    volumes:
      - bidpilot-redis-data:/data
'''
new = '''  redis:
    image: redis:7.4-alpine
    container_name: bidpilot-redis
    restart: unless-stopped
    environment:
      DOCPILOT_REDIS_PASSWORD: ${DOCPILOT_REDIS_PASSWORD:?DOCPILOT_REDIS_PASSWORD is required}
    command:
      - sh
      - -ec
      - 'exec redis-server --appendonly yes --requirepass "$$DOCPILOT_REDIS_PASSWORD"'
    ports:
      - "127.0.0.1:6379:6379"
    volumes:
      - bidpilot-redis-data:/data
'''
if "requirepass" in text and "DOCPILOT_REDIS_PASSWORD" in text:
    print("compose_redis_already_passworded")
elif old in text:
    compose.write_text(text.replace(old, new), encoding="utf-8")
    print("compose_redis_patched")
else:
    # fallback: if redis block differs, fail loud
    raise SystemExit("redis service block shape unexpected; aborting to avoid broken compose")
PY

echo "stopping api/worker"
docker compose stop api worker

echo "recreating redis"
docker compose up -d --force-recreate --no-deps redis

# Wait for redis auth ping
python3 - <<'PY'
import time, subprocess, re
from pathlib import Path
text = Path("/app/bidpilot/.env").read_text(encoding="utf-8", errors="replace")
password = ""
for line in text.splitlines():
    if line.startswith("DOCPILOT_REDIS_PASSWORD="):
        password = line.split("=", 1)[1].strip().strip('"').strip("'")
        break
if not password:
    raise SystemExit("missing redis password after write")
for i in range(30):
    r = subprocess.run(
        ["docker", "exec", "bidpilot-redis", "redis-cli", "--no-auth-warning", "-a", password, "PING"],
        capture_output=True, text=True,
    )
    if "PONG" in (r.stdout or ""):
        print("redis_auth_ok")
        break
    time.sleep(1)
else:
    raise SystemExit("redis did not accept password")
PY

echo "starting api/worker"
docker compose up -d --no-deps api worker

sleep 8
curl -fsS -o /dev/null -w "public_api:%{http_code}\n" https://bidpilot-api.rglens.com/health || true
curl -fsS -o /dev/null -w "public_web:%{http_code}\n" https://bidpilot.rglens.com/ || true
docker ps --filter name=bidpilot --format "table {{.Names}}\t{{.Status}}"
