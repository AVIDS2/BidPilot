from __future__ import annotations

import os


LOCAL_APP_URL = "http://localhost:5173"
LOCAL_API_URL = "http://localhost:8000"
LOCAL_CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
    "http://localhost:5175",
    "http://127.0.0.1:5175",
    "http://localhost:5176",
    "http://127.0.0.1:5176",
]
LOCAL_CORS_ORIGIN_REGEX = r"^https?://(?:localhost|127\.0\.0\.1)(?::\d+)?$"


def _clean_origin(value: str) -> str:
    return value.strip().rstrip("/")


def get_app_url() -> str:
    return _clean_origin(os.environ.get("DOCPILOT_APP_URL", LOCAL_APP_URL))


def get_api_url() -> str:
    return _clean_origin(os.environ.get("DOCPILOT_API_URL", LOCAL_API_URL))


def get_cors_origins() -> list[str]:
    raw = os.environ.get("DOCPILOT_CORS_ORIGINS")
    if not raw:
        return LOCAL_CORS_ORIGINS.copy()
    origins = [_clean_origin(item) for item in raw.split(",")]
    return [origin for origin in origins if origin]


def get_cors_origin_regex() -> str | None:
    """Allow arbitrary local Vite ports without loosening deployed environments."""
    environment = os.environ.get("DOCPILOT_ENV", "local").strip().lower()
    if environment in {"production", "staging"}:
        return None
    return LOCAL_CORS_ORIGIN_REGEX
