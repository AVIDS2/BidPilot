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
    assert "DOCPILOT_AUTH_REQUIRED must be true for production" in result.errors


def test_validate_environment_rejects_development_defaults() -> None:
    env = {
        "DOCPILOT_DATABASE_URL": "postgresql+psycopg://docpilot:docpilot@localhost:5433/docpilot",
        "DOCPILOT_REDIS_URL": "redis://localhost:6379/0",
        "DOCPILOT_MINIO_ENDPOINT": "localhost:9000",
        "DOCPILOT_MINIO_ACCESS_KEY": "docpilot",
        "DOCPILOT_MINIO_SECRET_KEY": "docpilot123",
        "DOCPILOT_JWT_SECRET": "dev-secret-change-in-production-32bytes!",
        "DOCPILOT_AUTH_REQUIRED": "false",
        "DOCPILOT_PROVIDER_DOMESTIC_API_KEY": "sk-local-development-placeholder",
    }

    result = production_readiness.validate_environment(env, target="production")

    assert result.ok is False
    assert "DOCPILOT_DATABASE_URL must not use localhost for production" in result.errors
    assert "DOCPILOT_REDIS_URL must not use localhost for production" in result.errors
    assert "DOCPILOT_MINIO_ENDPOINT must not use localhost for production" in result.errors
    assert "DOCPILOT_JWT_SECRET must not use the development default" in result.errors
    assert "DOCPILOT_AUTH_REQUIRED must be true for production" in result.errors
    assert "DOCPILOT_MINIO_ACCESS_KEY must not use the development default" in result.errors
    assert "DOCPILOT_MINIO_SECRET_KEY must not use the development default" in result.errors


def test_validate_environment_accepts_production_ready_shape() -> None:
    env = {
        "DOCPILOT_DATABASE_URL": "postgresql+psycopg://docpilot:secret@db.internal:5432/docpilot",
        "DOCPILOT_REDIS_URL": "redis://redis.internal:6379/0",
        "DOCPILOT_MINIO_ENDPOINT": "s3.internal.example.com",
        "DOCPILOT_MINIO_ACCESS_KEY": "prod-access-key",
        "DOCPILOT_MINIO_SECRET_KEY": "prod-storage-secret",
        "DOCPILOT_JWT_SECRET": "prod-secret-value-with-more-than-thirty-two-bytes",
        "DOCPILOT_AUTH_REQUIRED": "true",
        "DOCPILOT_PROVIDER_DOMESTIC_API_KEY": "prod-provider-key",
    }

    result = production_readiness.validate_environment(env, target="production")

    assert result.ok is True
    assert result.errors == []
