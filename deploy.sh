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
git pull --ff-only origin master

# Re-exec once so this run uses the just-pulled deploy.sh body
# (bash keeps the pre-pull script text in memory otherwise).
if [[ "${DOCPILOT_DEPLOY_REEXEC:-}" != "1" ]]; then
  export DOCPILOT_DEPLOY_REEXEC=1
  exec bash "$REPO_ROOT/deploy.sh" "$@"
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
    "DOCPILOT_ASSISTANT_ENGINE": "operator",
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
  docker compose up -d --build
else
  echo "deploy_mode=app_services_only"
  rm -f "$NEXT_COMPOSE_FILE"
  # Keep current topology. Rebuild application services only.
  # Prefer no-deps so a failing one-shot readiness/migrate job cannot strand api/web.
  docker compose build api worker web
  docker compose up -d --no-deps api worker web
fi

sleep 8
curl -fsS -o /dev/null -w "public_api:%{http_code}\n" https://bidpilot-api.rglens.com/health || true
curl -fsS -o /dev/null -w "public_web:%{http_code}\n" https://bidpilot.rglens.com/ || true
