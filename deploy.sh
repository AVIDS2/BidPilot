#!/usr/bin/env bash
set -euo pipefail

# BidPilot public deploy helper.
# Prefer versioned production compose only when the live .env can satisfy BOTH:
#   1) production compose interpolation (split passwords / minio keys)
#   2) scripts/production_readiness.py --target production required variables
# Otherwise keep the live compose topology and rebuild application services only.
#
# Important: do NOT shell-source .env (password special chars break set -a).
# Use Python to derive missing split vars and docker compose --env-file for runtime.

APP_ROOT=/app/bidpilot
REPO_ROOT="$APP_ROOT/repo"
COMPOSE_FILE="$APP_ROOT/docker-compose.yml"
NEXT_COMPOSE_FILE="$APP_ROOT/.docker-compose.next.yml"
ENV_FILE="$APP_ROOT/.env"

cd "$REPO_ROOT"
if [[ "${DOCPILOT_SKIP_PULL:-0}" != "1" ]]; then
  git pull --ff-only origin master

  # Re-exec once so this run uses the just-pulled deploy.sh body
  # (bash keeps the pre-pull script text in memory otherwise).
  if [[ "${DOCPILOT_DEPLOY_REEXEC:-}" != "1" ]]; then
    export DOCPILOT_DEPLOY_REEXEC=1
    exec bash "$REPO_ROOT/deploy.sh" "$@"
  fi
fi

# Derive split Postgres/Redis vars from URLs when missing.
python3 - <<'PY'
from pathlib import Path
from urllib.parse import urlparse, unquote

env_path = Path("/app/bidpilot/.env")
if not env_path.exists():
    print("derived_env 0")
    raise SystemExit(0)

text = env_path.read_text(encoding="utf-8", errors="replace")
vals = {}
for line in text.splitlines():
    if not line or line.strip().startswith("#") or "=" not in line:
        continue
    key, value = line.split("=", 1)
    vals[key.strip()] = value.strip().strip('"').strip("'")

additions = []
db_url = vals.get("DOCPILOT_DATABASE_URL") or vals.get("DATABASE_URL") or ""
parsed = urlparse(db_url)
if parsed.username and not vals.get("DOCPILOT_POSTGRES_USER"):
    additions.append(f"DOCPILOT_POSTGRES_USER={parsed.username}")
if parsed.password and not vals.get("DOCPILOT_POSTGRES_PASSWORD"):
    additions.append(f"DOCPILOT_POSTGRES_PASSWORD={unquote(parsed.password)}")
db_name = (parsed.path or "").lstrip("/")
if db_name and not vals.get("DOCPILOT_POSTGRES_DB"):
    additions.append(f"DOCPILOT_POSTGRES_DB={db_name}")

redis = urlparse(vals.get("DOCPILOT_REDIS_URL") or "")
if redis.password and not vals.get("DOCPILOT_REDIS_PASSWORD"):
    additions.append(f"DOCPILOT_REDIS_PASSWORD={unquote(redis.password)}")

# Soft production flags that readiness requires (safe defaults for live VPS).
soft_defaults = {
    "DOCPILOT_ENV": "production",
    "DOCPILOT_AGENT_CHECKPOINTER": vals.get("DOCPILOT_LANGGRAPH_CHECKPOINTER") or "postgres",
    "DOCPILOT_ASSISTANT_ENGINE": "pi",
    "USE_LANGGRAPH": "true",
    "DOCPILOT_RATE_LIMIT": "120/minute",
    "DOCPILOT_AUTH_REQUIRED": "true",
}
for key, value in soft_defaults.items():
    if not vals.get(key):
        additions.append(f"{key}={value}")

if additions:
    with env_path.open("a", encoding="utf-8") as fh:
        fh.write("\n# derived by deploy.sh\n")
        fh.write("\n".join(additions) + "\n")
print("derived_env", len(additions))
PY

cd "$APP_ROOT"

# Detect whether production compose + readiness can be satisfied from current .env.
use_full_compose=0
if python3 - <<'PY'
from pathlib import Path

env_path = Path("/app/bidpilot/.env")
if not env_path.exists():
    raise SystemExit(1)

text = env_path.read_text(encoding="utf-8", errors="replace")
keys = set()
for line in text.splitlines():
    if not line or line.strip().startswith("#") or "=" not in line:
        continue
    key, value = line.split("=", 1)
    if value.strip().strip('"').strip("'"):
        keys.add(key.strip())

# Compose interpolation needs.
compose_need = {
    "DOCPILOT_REDIS_PASSWORD",
    "DOCPILOT_POSTGRES_PASSWORD",
    "DOCPILOT_POSTGRES_USER",
    "DOCPILOT_POSTGRES_DB",
    "DOCPILOT_MINIO_ACCESS_KEY",
    "DOCPILOT_MINIO_SECRET_KEY",
}
# production_readiness.py --target production required variables (subset that
# commonly blocks the readiness container and freezes the whole stack).
readiness_need = {
    "DOCPILOT_DATABASE_URL",
    "DOCPILOT_REDIS_URL",
    "DOCPILOT_MINIO_ENDPOINT",
    "DOCPILOT_MINIO_ACCESS_KEY",
    "DOCPILOT_MINIO_SECRET_KEY",
    "DOCPILOT_JWT_SECRET",
    "DOCPILOT_AUTH_REQUIRED",
    "DOCPILOT_SECRETS_KEY",
    "DOCPILOT_APP_URL",
    "DOCPILOT_CORS_ORIGINS",
    "DOCPILOT_ENV",
    "DOCPILOT_LANGGRAPH_CHECKPOINTER",
    "DOCPILOT_AGENT_CHECKPOINTER",
    "DOCPILOT_ASSISTANT_ENGINE",
    "USE_LANGGRAPH",
    "DOCPILOT_POSTGRES_DB",
    "DOCPILOT_POSTGRES_USER",
    "DOCPILOT_POSTGRES_PASSWORD",
    "DOCPILOT_REDIS_PASSWORD",
    "DOCPILOT_RATE_LIMIT",
    "DOCPILOT_TRUSTED_PROXY_CIDRS",
    "DOCPILOT_OFFICIAL_MONTHLY_TOKEN_CEILING",
}
if "DOCPILOT_ASSISTANT_ENGINE" in keys:
    values = {}
    for line in text.splitlines():
        if not line or line.strip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    if values.get("DOCPILOT_ASSISTANT_ENGINE", "pi").lower() == "pi":
        readiness_need.add("DOCPILOT_PI_INTERNAL_SECRET")
need = compose_need | readiness_need
missing = sorted(need - keys)
if missing:
    print("full_compose_missing", ",".join(missing))
    raise SystemExit(1)
print("full_compose_env_ok")
raise SystemExit(0)
PY
then
  cp "$REPO_ROOT/docker-compose.production.yml" "$NEXT_COMPOSE_FILE"
  if docker compose -f "$NEXT_COMPOSE_FILE" --env-file .env config --quiet; then
    use_full_compose=1
  else
    echo "full_compose_config_invalid"
    rm -f "$NEXT_COMPOSE_FILE"
  fi
fi

if [[ "$use_full_compose" -eq 1 ]]; then
  echo "deploy_mode=full_production_compose"
  mv "$NEXT_COMPOSE_FILE" "$COMPOSE_FILE"
  # This VPS has limited RAM and no swap. Compose's default parallel build can
  # run several uv/pnpm/Vite processes at once and kill the web build before
  # any new container is started. Keep storage services running, free memory
  # from application containers, then build each image in a deterministic
  # sequence. A failed build restores the previous application containers.
  application_services=(api worker worker-beat pi-agent web)
  docker compose stop "${application_services[@]}" || true
  restore_application_services() {
    docker compose up -d --no-build "${application_services[@]}" || true
  }
  trap restore_application_services ERR
  for service in pi-agent api worker worker-beat web readiness migrate checkpoints; do
    echo "building_service=$service"
    docker compose build "$service"
  done
  trap - ERR
  docker compose up -d --no-build
else
  assistant_engine="$(python3 - <<'PY'
from pathlib import Path

value = "pi"
for line in Path("/app/bidpilot/.env").read_text(encoding="utf-8", errors="replace").splitlines():
    if line.startswith("DOCPILOT_ASSISTANT_ENGINE="):
        value = line.split("=", 1)[1].strip().strip('"').strip("'") or "pi"
        break
print(value.lower())
PY
)"
  if [[ "$assistant_engine" == "pi" ]]; then
    echo "fatal: Pi assistant requires the complete production compose topology; refusing a partial application-only deploy" >&2
    exit 1
  fi
  echo "deploy_mode=app_services_only"
  rm -f "$NEXT_COMPOSE_FILE"
  # Keep current topology. Rebuild application services only.
  # Prefer no-deps so an existing production topology remains untouched. The
  # migration itself is still mandatory: starting a newer API against an older
  # schema makes first tool execution fail after a seemingly healthy deploy.
  docker compose build api worker web
  echo "running_database_migrations"
  docker compose run --rm --no-deps api \
    /app/.venv/bin/alembic -c /app/services/api/alembic.ini upgrade head
  echo "initializing_langgraph_checkpoints"
  docker compose run --rm --no-deps api \
    /app/.venv/bin/python /app/scripts/setup_langgraph_checkpoints.py
  docker compose up -d --no-deps api worker web
fi

sleep 8
curl -fsS -o /dev/null -w "public_api:%{http_code}\n" https://bidpilot-api.rglens.com/health || true
curl -fsS -o /dev/null -w "public_web:%{http_code}\n" https://bidpilot.rglens.com/ || true
