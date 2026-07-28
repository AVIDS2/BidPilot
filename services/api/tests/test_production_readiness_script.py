import base64
import importlib.util
from pathlib import Path


_SCRIPT_PATH = Path(__file__).resolve().parents[3] / "scripts" / "production_readiness.py"
_SPEC = importlib.util.spec_from_file_location("production_readiness", _SCRIPT_PATH)
assert _SPEC is not None
production_readiness = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(production_readiness)


def test_validate_environment_reports_missing_required_variables() -> None:
    result = production_readiness.validate_environment({}, target="production")

    assert result.ok is False
    assert "DOCPILOT_DATABASE_URL is required" in result.errors
    assert "DOCPILOT_REDIS_URL is required" in result.errors
    assert "DOCPILOT_JWT_SECRET is required" in result.errors
    assert "DOCPILOT_SECRETS_KEY is required" in result.errors
    assert "DOCPILOT_AUTH_REQUIRED must be true for production" in result.errors
    assert "DOCPILOT_APP_URL is required" in result.errors
    assert "DOCPILOT_CORS_ORIGINS is required" in result.errors
    assert "DOCPILOT_LANGGRAPH_CHECKPOINTER is required" in result.errors
    assert "DOCPILOT_AGENT_CHECKPOINTER is required" in result.errors
    assert "DOCPILOT_ENV is required" in result.errors
    assert "DOCPILOT_ASSISTANT_ENGINE is required" in result.errors
    assert "USE_LANGGRAPH is required" in result.errors
    assert "DOCPILOT_POSTGRES_DB is required" in result.errors
    assert "DOCPILOT_POSTGRES_USER is required" in result.errors
    assert "DOCPILOT_POSTGRES_PASSWORD is required" in result.errors
    assert "DOCPILOT_REDIS_PASSWORD is required" in result.errors
    assert "DOCPILOT_RATE_LIMIT is required" in result.errors
    assert "DOCPILOT_TRUSTED_PROXY_CIDRS is required" in result.errors
    assert "DOCPILOT_OFFICIAL_MONTHLY_TOKEN_CEILING is required" in result.errors


def test_validate_environment_rejects_development_defaults() -> None:
    env = {
        "DOCPILOT_DATABASE_URL": "postgresql+psycopg://docpilot:docpilot@localhost:5433/docpilot",
        "DOCPILOT_REDIS_URL": "redis://localhost:6379/0",
        "DOCPILOT_MINIO_ENDPOINT": "localhost:9000",
        "DOCPILOT_MINIO_ACCESS_KEY": "docpilot",
        "DOCPILOT_MINIO_SECRET_KEY": "docpilot123",
        "DOCPILOT_JWT_SECRET": "dev-secret-change-in-production-32bytes!",
        "DOCPILOT_AUTH_REQUIRED": "false",
        "DOCPILOT_SECRETS_KEY": "not-a-fernet-key",
        "DOCPILOT_PROVIDER_DOMESTIC_API_KEY": "test-provider-key",
        "DOCPILOT_APP_URL": "http://localhost:5173",
        "DOCPILOT_CORS_ORIGINS": "http://localhost:5173",
        "DOCPILOT_LANGGRAPH_CHECKPOINTER": "memory",
        "DOCPILOT_AGENT_CHECKPOINTER": "memory",
        "DOCPILOT_ENV": "local",
        "DOCPILOT_ASSISTANT_ENGINE": "langgraph",
        "DOCPILOT_POSTGRES_DB": "bidpilot",
        "DOCPILOT_POSTGRES_USER": "bidpilot",
        "DOCPILOT_POSTGRES_PASSWORD": "bidpilot",
        "DOCPILOT_REDIS_PASSWORD": "redis",
    }

    result = production_readiness.validate_environment(env, target="production")

    assert result.ok is False
    assert "DOCPILOT_DATABASE_URL must not use localhost for production" in result.errors
    assert "DOCPILOT_REDIS_URL must not use localhost for production" in result.errors
    assert "DOCPILOT_MINIO_ENDPOINT must not use localhost for production" in result.errors
    assert "DOCPILOT_JWT_SECRET must not use the development default" in result.errors
    assert "DOCPILOT_AUTH_REQUIRED must be true for production" in result.errors
    assert "DOCPILOT_SECRETS_KEY must be a valid Fernet key" in result.errors
    assert "DOCPILOT_MINIO_ACCESS_KEY must not use the development default" in result.errors
    assert "DOCPILOT_MINIO_SECRET_KEY must not use the development default" in result.errors
    assert "DOCPILOT_APP_URL must be https for production" in result.errors
    assert "DOCPILOT_APP_URL must not use localhost for production" in result.errors
    assert "DOCPILOT_CORS_ORIGINS must not use localhost for production" in result.errors
    assert "DOCPILOT_LANGGRAPH_CHECKPOINTER must be postgres for production" in result.errors
    assert "DOCPILOT_AGENT_CHECKPOINTER must be postgres for production" in result.errors
    assert "DOCPILOT_ENV must be production for production deployment" in result.errors
    assert "DOCPILOT_ASSISTANT_ENGINE must be harness for production" in result.errors
    assert "USE_LANGGRAPH must be true for production workflows" in result.errors
    assert "DOCPILOT_SMTP_HOST is required for production email" in result.errors
    assert "DOCPILOT_SMTP_USER is required for production email" in result.errors
    assert "DOCPILOT_SMTP_PASS is required for production email" in result.errors
    assert "DOCPILOT_SMTP_FROM is required for production email" in result.errors
    assert "DOCPILOT_POSTGRES_PASSWORD must not use the development default" in result.errors
    assert "DOCPILOT_REDIS_PASSWORD must not use the development default" in result.errors
    assert "DOCPILOT_REDIS_URL must include a password for production" in result.errors


def test_validate_environment_accepts_production_ready_shape() -> None:
    env = {
        "DOCPILOT_DATABASE_URL": "postgresql+psycopg://docpilot:secret@db.internal:5432/docpilot",
        "DOCPILOT_REDIS_URL": "redis://:long-random-redis-password@redis.internal:6379/0",
        "DOCPILOT_MINIO_ENDPOINT": "s3.internal.example.com",
        "DOCPILOT_MINIO_ACCESS_KEY": "prod-access-key",
        "DOCPILOT_MINIO_SECRET_KEY": "prod-storage-secret",
        "DOCPILOT_JWT_SECRET": "prod-secret-value-with-more-than-thirty-two-bytes",
        "DOCPILOT_AUTH_REQUIRED": "true",
        "DOCPILOT_SECRETS_KEY": "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=",
        "DOCPILOT_PROVIDER_DOMESTIC_API_KEY": "prod-provider-key",
        "DOCPILOT_PROVIDER_DOMESTIC_MODEL": "qwen-plus",
        "DOCPILOT_APP_URL": "https://bidpilot.rglens.com",
        "DOCPILOT_CORS_ORIGINS": "https://bidpilot.rglens.com",
        "DOCPILOT_LANGGRAPH_CHECKPOINTER": "postgres",
        "DOCPILOT_AGENT_CHECKPOINTER": "postgres",
        "DOCPILOT_ENV": "production",
        "DOCPILOT_ASSISTANT_ENGINE": "harness",
        "USE_LANGGRAPH": "true",
        "DOCPILOT_POSTGRES_DB": "bidpilot",
        "DOCPILOT_POSTGRES_USER": "bidpilot",
        "DOCPILOT_POSTGRES_PASSWORD": "long-random-postgres-password",
        "DOCPILOT_REDIS_PASSWORD": "long-random-redis-password",
        "DOCPILOT_RATE_LIMIT": "1000/minute",
        "DOCPILOT_OFFICIAL_MONTHLY_TOKEN_CEILING": "100000",
        "DOCPILOT_TRUSTED_PROXY_CIDRS": "172.20.0.1/32",
        "DOCPILOT_SMTP_HOST": "smtp.qq.com",
        "DOCPILOT_SMTP_USER": "mailer@example.com",
        "DOCPILOT_SMTP_PASS": "smtp-app-password",
        "DOCPILOT_SMTP_FROM": "noreply@rglens.com",
    }

    result = production_readiness.validate_environment(env, target="production")

    assert result.ok is True
    assert result.errors == []

    env["DOCPILOT_ALLOW_STUB_LLM"] = "true"
    stub_enabled = production_readiness.validate_environment(env, target="production")
    assert stub_enabled.ok is False
    assert "DOCPILOT_ALLOW_STUB_LLM must not be enabled for production" in stub_enabled.errors

    env["DOCPILOT_ALLOW_STUB_LLM"] = "false"
    env["DOCPILOT_OFFICIAL_MONTHLY_TOKEN_CEILING"] = "-1"
    invalid_ceiling = production_readiness.validate_environment(env, target="production")
    assert invalid_ceiling.ok is False
    assert "DOCPILOT_OFFICIAL_MONTHLY_TOKEN_CEILING must be a non-negative integer" in invalid_ceiling.errors


def test_validate_environment_rejects_legacy_assistant_engine_aliases() -> None:
    env = {
        "DOCPILOT_DATABASE_URL": "postgresql+psycopg://docpilot:secret@db.internal:5432/docpilot",
        "DOCPILOT_REDIS_URL": "redis://:long-random-redis-password@redis.internal:6379/0",
        "DOCPILOT_MINIO_ENDPOINT": "s3.internal.example.com",
        "DOCPILOT_MINIO_ACCESS_KEY": "prod-access-key",
        "DOCPILOT_MINIO_SECRET_KEY": "prod-storage-secret",
        "DOCPILOT_JWT_SECRET": "prod-secret-value-with-more-than-thirty-two-bytes",
        "DOCPILOT_AUTH_REQUIRED": "true",
        "DOCPILOT_SECRETS_KEY": "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=",
        "DOCPILOT_PROVIDER_DOMESTIC_API_KEY": "prod-provider-key",
        "DOCPILOT_PROVIDER_DOMESTIC_MODEL": "qwen-plus",
        "DOCPILOT_APP_URL": "https://bidpilot.rglens.com",
        "DOCPILOT_CORS_ORIGINS": "https://bidpilot.rglens.com",
        "DOCPILOT_LANGGRAPH_CHECKPOINTER": "postgres",
        "DOCPILOT_AGENT_CHECKPOINTER": "postgres",
        "DOCPILOT_ENV": "production",
        "USE_LANGGRAPH": "true",
        "DOCPILOT_POSTGRES_DB": "bidpilot",
        "DOCPILOT_POSTGRES_USER": "bidpilot",
        "DOCPILOT_POSTGRES_PASSWORD": "long-random-postgres-password",
        "DOCPILOT_REDIS_PASSWORD": "long-random-redis-password",
        "DOCPILOT_RATE_LIMIT": "1000/minute",
        "DOCPILOT_OFFICIAL_MONTHLY_TOKEN_CEILING": "100000",
        "DOCPILOT_TRUSTED_PROXY_CIDRS": "172.20.0.1/32",
        "DOCPILOT_SMTP_HOST": "smtp.qq.com",
        "DOCPILOT_SMTP_USER": "mailer@example.com",
        "DOCPILOT_SMTP_PASS": "smtp-app-password",
        "DOCPILOT_SMTP_FROM": "noreply@rglens.com",
    }

    for alias in ("operator", "streaming_harness"):
        env["DOCPILOT_ASSISTANT_ENGINE"] = alias
        result = production_readiness.validate_environment(env, target="production")

        assert result.ok is False
        assert "DOCPILOT_ASSISTANT_ENGINE must be harness for production" in result.errors


def test_validate_environment_requires_a_complete_platform_assistant_model() -> None:
    env = {
        "DOCPILOT_DATABASE_URL": "postgresql+psycopg://docpilot:secret@db.internal:5432/docpilot",
        "DOCPILOT_REDIS_URL": "redis://:long-random-redis-password@redis.internal:6379/0",
        "DOCPILOT_MINIO_ENDPOINT": "s3.internal.example.com",
        "DOCPILOT_MINIO_ACCESS_KEY": "prod-access-key",
        "DOCPILOT_MINIO_SECRET_KEY": "prod-storage-secret",
        "DOCPILOT_JWT_SECRET": "prod-secret-value-with-more-than-thirty-two-bytes",
        "DOCPILOT_AUTH_REQUIRED": "true",
        "DOCPILOT_SECRETS_KEY": "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=",
        "DEEPSEEK_API_KEY": "prod-provider-key",
        "DOCPILOT_APP_URL": "https://bidpilot.rglens.com",
        "DOCPILOT_CORS_ORIGINS": "https://bidpilot.rglens.com",
        "DOCPILOT_LANGGRAPH_CHECKPOINTER": "postgres",
        "DOCPILOT_AGENT_CHECKPOINTER": "postgres",
        "DOCPILOT_ENV": "production",
        "DOCPILOT_ASSISTANT_ENGINE": "harness",
        "USE_LANGGRAPH": "true",
        "DOCPILOT_POSTGRES_DB": "bidpilot",
        "DOCPILOT_POSTGRES_USER": "bidpilot",
        "DOCPILOT_POSTGRES_PASSWORD": "long-random-postgres-password",
        "DOCPILOT_REDIS_PASSWORD": "long-random-redis-password",
        "DOCPILOT_RATE_LIMIT": "1000/minute",
        "DOCPILOT_OFFICIAL_MONTHLY_TOKEN_CEILING": "100000",
        "DOCPILOT_TRUSTED_PROXY_CIDRS": "172.20.0.1/32",
        "DOCPILOT_SMTP_HOST": "smtp.qq.com",
        "DOCPILOT_SMTP_USER": "mailer@example.com",
        "DOCPILOT_SMTP_PASS": "smtp-app-password",
        "DOCPILOT_SMTP_FROM": "noreply@rglens.com",
    }

    env["DOCPILOT_SECRETS_KEY"] = base64.urlsafe_b64encode(b"0" * 32).decode()
    result = production_readiness.validate_environment(env, target="production")

    assert result.ok is False
    assert "a complete platform assistant model configuration (API key and model name) is required" in result.errors

    env["DEEPSEEK_MODEL"] = "configured-model"
    assert production_readiness.validate_environment(env, target="production").ok is True


def test_validate_environment_rejects_invalid_trusted_proxy_and_rate_limit() -> None:
    env = {
        "DOCPILOT_DATABASE_URL": "postgresql+psycopg://bidpilot:fixture@db.internal:5432/bidpilot",
        "DOCPILOT_REDIS_URL": "redis://:fixture-redis-password@redis.internal:6379/0",
        "DOCPILOT_MINIO_ENDPOINT": "s3.internal.example.com",
        "DOCPILOT_MINIO_ACCESS_KEY": "prod-access-key",
        "DOCPILOT_MINIO_SECRET_KEY": "prod-storage-secret",
        "DOCPILOT_JWT_SECRET": "prod-secret-value-with-more-than-thirty-two-bytes",
        "DOCPILOT_AUTH_REQUIRED": "true",
        "DOCPILOT_SECRETS_KEY": "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=",
        "DOCPILOT_PROVIDER_DOMESTIC_API_KEY": "prod-provider-key",
        "DOCPILOT_APP_URL": "https://bidpilot.rglens.com",
        "DOCPILOT_CORS_ORIGINS": "https://bidpilot.rglens.com",
        "DOCPILOT_LANGGRAPH_CHECKPOINTER": "postgres",
        "DOCPILOT_AGENT_CHECKPOINTER": "postgres",
        "DOCPILOT_ENV": "production",
        "DOCPILOT_ASSISTANT_ENGINE": "harness",
        "DOCPILOT_POSTGRES_DB": "bidpilot",
        "DOCPILOT_POSTGRES_USER": "bidpilot",
        "DOCPILOT_POSTGRES_PASSWORD": "long-random-postgres-password",
        "DOCPILOT_REDIS_PASSWORD": "long-random-redis-password",
        "DOCPILOT_RATE_LIMIT": "many/week",
        "DOCPILOT_TRUSTED_PROXY_CIDRS": "not-a-cidr",
        "DOCPILOT_SMTP_HOST": "smtp.example.test",
        "DOCPILOT_SMTP_USER": "mailer@example.test",
        "DOCPILOT_SMTP_PASS": "smtp-app-password",
        "DOCPILOT_SMTP_FROM": "noreply@example.test",
    }

    result = production_readiness.validate_environment(env, target="production")

    assert result.ok is False
    assert "DOCPILOT_RATE_LIMIT must use '<positive integer>/<second|minute|hour|day>'" in result.errors
    assert "DOCPILOT_TRUSTED_PROXY_CIDRS must contain one or more valid IPs or CIDRs" in result.errors


def test_validate_environment_rejects_partial_stripe_billing_configuration() -> None:
    env = {
        "DOCPILOT_DATABASE_URL": "postgresql+psycopg://docpilot:secret@db.internal:5432/docpilot",
        "DOCPILOT_REDIS_URL": "redis://:long-random-redis-password@redis.internal:6379/0",
        "DOCPILOT_MINIO_ENDPOINT": "s3.internal.example.com",
        "DOCPILOT_MINIO_ACCESS_KEY": "prod-access-key",
        "DOCPILOT_MINIO_SECRET_KEY": "prod-storage-secret",
        "DOCPILOT_JWT_SECRET": "prod-secret-value-with-more-than-thirty-two-bytes",
        "DOCPILOT_AUTH_REQUIRED": "true",
        "DOCPILOT_SECRETS_KEY": "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=",
        "DOCPILOT_PROVIDER_DOMESTIC_API_KEY": "prod-provider-key",
        "DOCPILOT_APP_URL": "https://bidpilot.rglens.com",
        "DOCPILOT_CORS_ORIGINS": "https://bidpilot.rglens.com",
        "DOCPILOT_LANGGRAPH_CHECKPOINTER": "postgres",
        "DOCPILOT_AGENT_CHECKPOINTER": "postgres",
        "DOCPILOT_ENV": "production",
        "DOCPILOT_ASSISTANT_ENGINE": "harness",
        "DOCPILOT_POSTGRES_DB": "bidpilot",
        "DOCPILOT_POSTGRES_USER": "bidpilot",
        "DOCPILOT_POSTGRES_PASSWORD": "long-random-postgres-password",
        "DOCPILOT_REDIS_PASSWORD": "long-random-redis-password",
        "DOCPILOT_RATE_LIMIT": "1000/minute",
        "DOCPILOT_TRUSTED_PROXY_CIDRS": "172.20.0.1/32",
        "DOCPILOT_SMTP_HOST": "smtp.qq.com",
        "DOCPILOT_SMTP_USER": "mailer@example.com",
        "DOCPILOT_SMTP_PASS": "smtp-app-password",
        "DOCPILOT_SMTP_FROM": "noreply@rglens.com",
        "DOCPILOT_STRIPE_SECRET_KEY": "sk_test_fixture",
    }

    result = production_readiness.validate_environment(env, target="production")

    assert result.ok is False
    assert "DOCPILOT_STRIPE_WEBHOOK_SECRET is required when Stripe billing is enabled" in result.errors
    assert "DOCPILOT_STRIPE_PRO_PRICE_ID is required when Stripe billing is enabled" in result.errors
    assert "DOCPILOT_STRIPE_SECRET_KEY must use a Stripe live-mode secret key for production" in result.errors


def test_validate_environment_rejects_placeholder_values() -> None:
    env = {
        "DOCPILOT_DATABASE_URL": "postgresql+psycopg://bidpilot:secret@postgres:5432/bidpilot",
        "DOCPILOT_REDIS_URL": "redis://:long-random-redis-password@redis:6379/0",
        "DOCPILOT_MINIO_ENDPOINT": "minio:9000",
        "DOCPILOT_MINIO_ACCESS_KEY": "replace-with-access-key",
        "DOCPILOT_MINIO_SECRET_KEY": "long-random-storage-secret",
        "DOCPILOT_JWT_SECRET": "prod-secret-value-with-more-than-thirty-two-bytes",
        "DOCPILOT_AUTH_REQUIRED": "true",
        "DOCPILOT_SECRETS_KEY": "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=",
        "DOCPILOT_PROVIDER_DOMESTIC_API_KEY": "replace-with-provider-key",
        "DOCPILOT_APP_URL": "https://bidpilot.rglens.com",
        "DOCPILOT_CORS_ORIGINS": "https://bidpilot.rglens.com",
        "DOCPILOT_LANGGRAPH_CHECKPOINTER": "postgres",
        "DOCPILOT_AGENT_CHECKPOINTER": "postgres",
        "DOCPILOT_ENV": "production",
        "DOCPILOT_ASSISTANT_ENGINE": "harness",
        "DOCPILOT_POSTGRES_DB": "bidpilot",
        "DOCPILOT_POSTGRES_USER": "bidpilot",
        "DOCPILOT_POSTGRES_PASSWORD": "long-random-postgres-password",
        "DOCPILOT_REDIS_PASSWORD": "long-random-redis-password",
        "DOCPILOT_SMTP_HOST": "smtp.example.test",
        "DOCPILOT_SMTP_USER": "mailer@example.test",
        "DOCPILOT_SMTP_PASS": "smtp-app-password",
        "DOCPILOT_SMTP_FROM": "noreply@example.test",
    }

    result = production_readiness.validate_environment(env, target="production")

    assert result.ok is False
    assert "DOCPILOT_MINIO_ACCESS_KEY must not use a placeholder value" in result.errors
    assert "one provider API key is required" in result.errors


def test_production_compose_reads_infrastructure_credentials_from_server_env() -> None:
    repository_root = Path(__file__).resolve().parents[3]
    compose = (repository_root / "docker-compose.production.yml").read_text(encoding="utf-8")

    assert "POSTGRES_PASSWORD: ${DOCPILOT_POSTGRES_PASSWORD:?DOCPILOT_POSTGRES_PASSWORD is required}" in compose
    assert "MINIO_ROOT_USER: ${DOCPILOT_MINIO_ACCESS_KEY:?DOCPILOT_MINIO_ACCESS_KEY is required}" in compose
    assert "MINIO_ROOT_PASSWORD: ${DOCPILOT_MINIO_SECRET_KEY:?DOCPILOT_MINIO_SECRET_KEY is required}" in compose
    assert "DOCPILOT_REDIS_PASSWORD: ${DOCPILOT_REDIS_PASSWORD:?DOCPILOT_REDIS_PASSWORD is required}" in compose
    assert "--requirepass \"$$DOCPILOT_REDIS_PASSWORD\"" in compose
    assert "bidpilot-readiness" in compose
    assert '"/app/scripts/production_readiness.py", "--target", "production"' in compose
    assert "readiness:\n        condition: service_completed_successfully" in compose
    assert "/health/ready" in compose
    assert "condition: service_healthy" in compose
    worker_section = compose.split("  worker:\n", 1)[1].split("  worker-beat:", 1)[0]
    assert 'USE_LANGGRAPH: "true"' in worker_section
    assert "POSTGRES_PASSWORD: bidpilot" not in compose
    assert "MINIO_ROOT_PASSWORD: bidpilot123" not in compose


def test_fallback_deploy_runs_migrations_before_restarting_application_services() -> None:
    repository_root = Path(__file__).resolve().parents[3]
    deploy_script = (repository_root / "deploy.sh").read_text(encoding="utf-8")
    migrate_command = "docker compose run --rm --no-deps api"
    restart_command = "docker compose up -d --no-deps api worker web"

    assert migrate_command in deploy_script
    assert deploy_script.index(migrate_command) < deploy_script.index(restart_command)


def test_release_workflow_injects_the_full_production_readiness_contract() -> None:
    repository_root = Path(__file__).resolve().parents[3]
    workflow = (repository_root / ".github" / "workflows" / "release.yml").read_text(
        encoding="utf-8"
    )

    required_variables = (
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
        "DOCPILOT_SMTP_HOST",
        "DOCPILOT_SMTP_USER",
        "DOCPILOT_SMTP_PASS",
        "DOCPILOT_SMTP_FROM",
    )

    for name in required_variables:
        assert f"{name}:" in workflow
    assert "redis://${{ secrets.DOCPILOT_REDIS_HOST }}:6379/0" not in workflow
    assert (
        "redis://:${{ secrets.DOCPILOT_REDIS_PASSWORD }}@"
        "${{ secrets.DOCPILOT_REDIS_HOST }}:6379/0"
    ) in workflow
