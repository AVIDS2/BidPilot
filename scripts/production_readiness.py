from __future__ import annotations

import argparse
import base64
import ipaddress
import os
import re
from typing import Mapping, NamedTuple
from urllib.parse import urlsplit


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
    "DOCPILOT_ENV",
    "DOCPILOT_LANGGRAPH_CHECKPOINTER",
    "DOCPILOT_AGENT_CHECKPOINTER",
    "DOCPILOT_ASSISTANT_ENGINE",
    "DOCPILOT_PI_INTERNAL_SECRET",
    "USE_LANGGRAPH",
    "DOCPILOT_POSTGRES_DB",
    "DOCPILOT_POSTGRES_USER",
    "DOCPILOT_POSTGRES_PASSWORD",
    "DOCPILOT_REDIS_PASSWORD",
    "DOCPILOT_RATE_LIMIT",
    "DOCPILOT_TRUSTED_PROXY_CIDRS",
    "DOCPILOT_OFFICIAL_MONTHLY_TOKEN_CEILING",
]

PROVIDER_KEY_VARIABLES = [
    "DOCPILOT_ASSISTANT_API_KEY",
    "OPENCODE_API_KEY",
    "DOCPILOT_PROVIDER_OPENAI_API_KEY",
    "DOCPILOT_PROVIDER_DOMESTIC_API_KEY",
    "DEEPSEEK_API_KEY",
    "ALIYUN_API_KEY",
    "DASHSCOPE_API_KEY",
    "OPENAI_API_KEY",
    "LLM_API_KEY",
]

SMTP_PRODUCTION_VARIABLES = [
    "DOCPILOT_SMTP_HOST",
    "DOCPILOT_SMTP_USER",
    "DOCPILOT_SMTP_PASS",
    "DOCPILOT_SMTP_FROM",
]
RESEND_PRODUCTION_KEY_VARIABLES = [
    "DOCPILOT_RESEND_API_KEY",
    "RESEND_API_KEY",
]
RESEND_DEFAULT_FROM = "BidPilot <notifications@updates.rglens.com>"

STRIPE_BILLING_REQUIRED_IF_ENABLED = [
    "DOCPILOT_STRIPE_SECRET_KEY",
    "DOCPILOT_STRIPE_WEBHOOK_SECRET",
    "DOCPILOT_STRIPE_PRO_PRICE_ID",
]
STRIPE_BILLING_OPTIONAL = ["DOCPILOT_STRIPE_ENTERPRISE_PRICE_ID"]

_PLACEHOLDER_PREFIXES = ("replace", "change", "your", "example", "<")
_PLACEHOLDER_VALUES = {"todo", "tbd", "none", "null", "password", "secret"}
_WEAK_POSTGRES_PASSWORDS = {"bidpilot", "bidpilot123", "docpilot", "docpilot123"}
_WEAK_REDIS_PASSWORDS = {"redis", "redis123", "bidpilot", "bidpilot123", "docpilot", "docpilot123"}
_RATE_LIMIT_PATTERN = re.compile(r"^(?P<count>[1-9][0-9]*)/(?P<window>second|seconds|minute|minutes|hour|hours|day|days)$")
_NON_NEGATIVE_INTEGER_PATTERN = re.compile(r"^(0|[1-9][0-9]*)$")
_CANONICAL_ASSISTANT_ENGINE = "pi"


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


def _is_placeholder(value: str) -> bool:
    normalized = value.strip().casefold()
    return normalized in _PLACEHOLDER_VALUES or normalized.startswith(_PLACEHOLDER_PREFIXES)


def _is_valid_rate_limit(value: str) -> bool:
    return bool(_RATE_LIMIT_PATTERN.fullmatch(value.strip().lower()))


def _is_configured_model_value(env: Mapping[str, str], name: str) -> bool:
    value = env.get(name)
    return not _is_missing(value) and not _is_placeholder(value or "")


def _has_complete_platform_assistant_model(env: Mapping[str, str]) -> bool:
    """Match the server-side resolver without calling an external provider.

    A deployment can prove that it has a key/model pair, but it cannot safely
    infer which model a custom gateway supports. Endpoint compatibility stays
    an explicit administrator choice and is surfaced by the runtime in a
    redacted error if the provider rejects it.
    """

    assistant_key = _is_configured_model_value(env, "DOCPILOT_ASSISTANT_API_KEY")
    assistant_model = any(
        _is_configured_model_value(env, name)
        for name in ("DOCPILOT_ASSISTANT_MODEL", "DEEPSEEK_MODEL")
    )
    if assistant_key and assistant_model:
        return True

    # OpenCode Go defaults to the reviewed OpenAI-compatible endpoint and
    # `deepseek-v4-flash` profile. Treat it like the official DeepSeek default:
    # this is a code-level contract, not an arbitrary gateway inference.
    if _is_configured_model_value(env, "OPENCODE_API_KEY"):
        return True

    # DeepSeek defaults to the explicitly supported platform model
    # ``deepseek-v4-flash`` when no override is supplied. This is a code-level
    # deployment contract, unlike an arbitrary custom gateway model.
    if _is_configured_model_value(env, "DEEPSEEK_API_KEY"):
        return True

    domestic_key = any(
        _is_configured_model_value(env, name)
        for name in (
            "DOCPILOT_PROVIDER_DOMESTIC_API_KEY",
            "ALIYUN_API_KEY",
            "DASHSCOPE_API_KEY",
        )
    )
    domestic_model = any(
        _is_configured_model_value(env, name)
        for name in ("DOCPILOT_PROVIDER_DOMESTIC_MODEL", "DOCPILOT_LLM_MODEL_PRIMARY")
    )
    return domestic_key and domestic_model


def _has_valid_proxy_cidrs(value: str) -> bool:
    candidates = [item.strip() for item in value.split(",") if item.strip()]
    if not candidates:
        return False
    try:
        for candidate in candidates:
            ipaddress.ip_network(candidate, strict=False)
    except ValueError:
        return False
    return True


def validate_environment(env: Mapping[str, str], target: str) -> ReadinessResult:
    errors: list[str] = []
    warnings: list[str] = []
    normalized_target = target.lower()

    if normalized_target != "production":
        warnings.append(f"target {target} uses production parity checks only for documented deployment gates")

    for name in REQUIRED_PRODUCTION_VARIABLES:
        if _is_missing(env.get(name)):
            errors.append(f"{name} is required")
        elif _is_placeholder(env[name]):
            errors.append(f"{name} must not use a placeholder value")

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

    if env.get("DOCPILOT_AGENT_CHECKPOINTER") != "postgres":
        errors.append("DOCPILOT_AGENT_CHECKPOINTER must be postgres for production")

    if (env.get("DOCPILOT_ENV") or "").lower() != "production":
        errors.append("DOCPILOT_ENV must be production for production deployment")

    assistant_engine = (env.get("DOCPILOT_ASSISTANT_ENGINE") or "").lower()
    if assistant_engine != _CANONICAL_ASSISTANT_ENGINE:
        errors.append("DOCPILOT_ASSISTANT_ENGINE must be pi for production")

    pi_internal_secret = env.get("DOCPILOT_PI_INTERNAL_SECRET")
    if pi_internal_secret and len(pi_internal_secret) < 32:
        errors.append("DOCPILOT_PI_INTERNAL_SECRET must be at least 32 characters")

    if env.get("USE_LANGGRAPH", "").lower() not in {"1", "true", "yes"}:
        errors.append("USE_LANGGRAPH must be true for production workflows")

    if env.get("DOCPILOT_ALLOW_STUB_LLM", "").lower() in {"1", "true", "yes"}:
        errors.append("DOCPILOT_ALLOW_STUB_LLM must not be enabled for production")

    rate_limit = env.get("DOCPILOT_RATE_LIMIT")
    if rate_limit and not _is_valid_rate_limit(rate_limit):
        errors.append("DOCPILOT_RATE_LIMIT must use '<positive integer>/<second|minute|hour|day>'")

    trusted_proxy_cidrs = env.get("DOCPILOT_TRUSTED_PROXY_CIDRS")
    if trusted_proxy_cidrs and not _has_valid_proxy_cidrs(trusted_proxy_cidrs):
        errors.append("DOCPILOT_TRUSTED_PROXY_CIDRS must contain one or more valid IPs or CIDRs")

    official_token_ceiling = env.get("DOCPILOT_OFFICIAL_MONTHLY_TOKEN_CEILING", "")
    if official_token_ceiling and not _NON_NEGATIVE_INTEGER_PATTERN.fullmatch(official_token_ceiling.strip()):
        errors.append("DOCPILOT_OFFICIAL_MONTHLY_TOKEN_CEILING must be a non-negative integer")

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

    resend_key = next(
        (
            env[name]
            for name in RESEND_PRODUCTION_KEY_VARIABLES
            if not _is_missing(env.get(name)) and not _is_placeholder(env[name])
        ),
        None,
    )
    resend_sender = env.get("DOCPILOT_RESEND_FROM", RESEND_DEFAULT_FROM)
    resend_sender_valid = not _is_missing(resend_sender) and not _is_placeholder(resend_sender)

    for name in RESEND_PRODUCTION_KEY_VARIABLES:
        value = env.get(name)
        if value and _is_placeholder(value):
            errors.append(f"{name} must not use a placeholder value")
    if env.get("DOCPILOT_RESEND_FROM") and _is_placeholder(env["DOCPILOT_RESEND_FROM"]):
        errors.append("DOCPILOT_RESEND_FROM must not use a placeholder value")

    if not resend_key or not resend_sender_valid:
        for name in SMTP_PRODUCTION_VARIABLES:
            if _is_missing(env.get(name)):
                errors.append(f"{name} is required for production email")
            elif _is_placeholder(env[name]):
                errors.append(f"{name} must not use a placeholder value")

    if not any(
        not _is_missing(env.get(name)) and not _is_placeholder(env[name])
        for name in PROVIDER_KEY_VARIABLES
    ):
        errors.append("one provider API key is required")

    if not _has_complete_platform_assistant_model(env):
        errors.append("a complete platform assistant model configuration (API key and model name) is required")

    stripe_values = [env.get(name) for name in (*STRIPE_BILLING_REQUIRED_IF_ENABLED, *STRIPE_BILLING_OPTIONAL)]
    if any(not _is_missing(value) for value in stripe_values):
        for name in STRIPE_BILLING_REQUIRED_IF_ENABLED:
            value = env.get(name)
            if _is_missing(value):
                errors.append(f"{name} is required when Stripe billing is enabled")
            elif _is_placeholder(value):
                errors.append(f"{name} must not use a placeholder value when Stripe billing is enabled")
        for name in STRIPE_BILLING_OPTIONAL:
            value = env.get(name)
            if value and _is_placeholder(value):
                errors.append(f"{name} must not use a placeholder value when set")
        stripe_secret_key = env.get("DOCPILOT_STRIPE_SECRET_KEY", "")
        if target == "production" and stripe_secret_key and not stripe_secret_key.startswith("sk_live_"):
            errors.append(
                "DOCPILOT_STRIPE_SECRET_KEY must use a Stripe live-mode secret key for production"
            )

    postgres_password = env.get("DOCPILOT_POSTGRES_PASSWORD")
    if postgres_password and postgres_password.casefold() in _WEAK_POSTGRES_PASSWORDS:
        errors.append("DOCPILOT_POSTGRES_PASSWORD must not use the development default")

    redis_password = env.get("DOCPILOT_REDIS_PASSWORD")
    if redis_password and redis_password.casefold() in _WEAK_REDIS_PASSWORDS:
        errors.append("DOCPILOT_REDIS_PASSWORD must not use the development default")
    redis_url = env.get("DOCPILOT_REDIS_URL")
    if redis_url and not _redis_url_has_password(redis_url):
        errors.append("DOCPILOT_REDIS_URL must include a password for production")
    rate_limit_storage_uri = env.get("DOCPILOT_RATE_LIMIT_STORAGE_URI")
    if rate_limit_storage_uri:
        if _uses_localhost(rate_limit_storage_uri):
            errors.append("DOCPILOT_RATE_LIMIT_STORAGE_URI must not use localhost for production")
        if not _redis_url_has_password(rate_limit_storage_uri):
            errors.append("DOCPILOT_RATE_LIMIT_STORAGE_URI must include a password for production")

    return ReadinessResult(ok=len(errors) == 0, errors=errors, warnings=warnings)


def _redis_url_has_password(value: str) -> bool:
    try:
        return bool(urlsplit(value).password)
    except ValueError:
        return False


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
