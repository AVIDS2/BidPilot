from __future__ import annotations

import argparse
import base64
import os
from typing import Mapping, NamedTuple


DEVELOPMENT_DEFAULTS = {
    "DOCPILOT_DATABASE_URL": {
        "postgresql+psycopg://docpilot:docpilot@localhost:5433/docpilot",
        "postgresql://docpilot:docpilot@localhost:5433/docpilot",
        "postgresql://docpilot:docpilot123@localhost:5433/docpilot",
    },
    "DOCPILOT_REDIS_URL": {"redis://localhost:6379/0"},
    "DOCPILOT_MINIO_ENDPOINT": {"localhost:9000"},
    "DOCPILOT_MINIO_ACCESS_KEY": {"docpilot"},
    "DOCPILOT_MINIO_SECRET_KEY": {"docpilot123"},
    "DOCPILOT_JWT_SECRET": {"dev-secret-change-in-production-32bytes!"},
}

REQUIRED_PRODUCTION_VARIABLES = [
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
    "DOCPILOT_LANGGRAPH_CHECKPOINTER",
]

PROVIDER_KEY_VARIABLES = [
    "DOCPILOT_PROVIDER_OPENAI_API_KEY",
    "DOCPILOT_PROVIDER_DOMESTIC_API_KEY",
    "ALIYUN_API_KEY",
    "DASHSCOPE_API_KEY",
    "OPENAI_API_KEY",
    "LLM_API_KEY",
]

SMTP_PRODUCTION_VARIABLES = [
    "DOCPILOT_SMTP_HOST",
    "DOCPILOT_SMTP_USER",
    "DOCPILOT_SMTP_FROM",
]


class ReadinessResult(NamedTuple):
    ok: bool
    errors: list[str]
    warnings: list[str]


def _is_missing(value: str | None) -> bool:
    return value is None or value.strip() == ""


def _uses_localhost(value: str) -> bool:
    lower = value.lower()
    return "localhost" in lower or "127.0.0.1" in lower


def _is_https_url(value: str) -> bool:
    return value.lower().startswith("https://")


def _is_fernet_key(value: str) -> bool:
    try:
        decoded = base64.urlsafe_b64decode(value.encode("utf-8"))
    except Exception:
        return False
    return len(decoded) == 32


def validate_environment(env: Mapping[str, str], target: str) -> ReadinessResult:
    errors: list[str] = []
    warnings: list[str] = []
    normalized_target = target.lower()

    if normalized_target != "production":
        warnings.append(f"target {target} uses production parity checks only for documented deployment gates")

    for name in REQUIRED_PRODUCTION_VARIABLES:
        if _is_missing(env.get(name)):
            errors.append(f"{name} is required")

    if env.get("DOCPILOT_AUTH_REQUIRED", "").lower() != "true":
        errors.append("DOCPILOT_AUTH_REQUIRED must be true for production")

    app_url = env.get("DOCPILOT_APP_URL")
    if app_url:
        if not _is_https_url(app_url):
            errors.append("DOCPILOT_APP_URL must be https for production")
        if _uses_localhost(app_url):
            errors.append("DOCPILOT_APP_URL must not use localhost for production")

    cors_origins = env.get("DOCPILOT_CORS_ORIGINS")
    if cors_origins and _uses_localhost(cors_origins):
        errors.append("DOCPILOT_CORS_ORIGINS must not use localhost for production")
    if app_url and cors_origins:
        normalized_origins = [item.strip().rstrip("/") for item in cors_origins.split(",") if item.strip()]
        if app_url.rstrip("/") not in normalized_origins:
            errors.append("DOCPILOT_CORS_ORIGINS must include DOCPILOT_APP_URL")

    if env.get("DOCPILOT_LANGGRAPH_CHECKPOINTER") != "postgres":
        errors.append("DOCPILOT_LANGGRAPH_CHECKPOINTER must be postgres for production")

    for name, defaults in DEVELOPMENT_DEFAULTS.items():
        value = env.get(name)
        if value in defaults:
            errors.append(f"{name} must not use the development default")

    for name in ["DOCPILOT_DATABASE_URL", "DOCPILOT_REDIS_URL", "DOCPILOT_MINIO_ENDPOINT"]:
        value = env.get(name)
        if value and _uses_localhost(value):
            errors.append(f"{name} must not use localhost for production")

    jwt_secret = env.get("DOCPILOT_JWT_SECRET")
    if jwt_secret and len(jwt_secret) < 32:
        errors.append("DOCPILOT_JWT_SECRET must be at least 32 characters")

    secrets_key = env.get("DOCPILOT_SECRETS_KEY")
    if secrets_key and not _is_fernet_key(secrets_key):
        errors.append("DOCPILOT_SECRETS_KEY must be a valid Fernet key")

    for name in SMTP_PRODUCTION_VARIABLES:
        if _is_missing(env.get(name)):
            errors.append(f"{name} is required for production email")

    if not any(not _is_missing(env.get(name)) for name in PROVIDER_KEY_VARIABLES):
        errors.append("one provider API key is required")

    return ReadinessResult(ok=len(errors) == 0, errors=errors, warnings=warnings)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate DocPilot deployment readiness environment variables.")
    parser.add_argument("--target", choices=["staging", "production"], default="production")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = validate_environment(os.environ, target=args.target)

    for warning in result.warnings:
        print(f"warning: {warning}")
    for error in result.errors:
        print(f"error: {error}")
    if result.ok:
        print(f"{args.target} readiness check passed")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
