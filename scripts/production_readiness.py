from __future__ import annotations

import argparse
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
]

PROVIDER_KEY_VARIABLES = [
    "DOCPILOT_PROVIDER_OPENAI_API_KEY",
    "DOCPILOT_PROVIDER_DOMESTIC_API_KEY",
    "OPENAI_API_KEY",
    "LLM_API_KEY",
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
