from __future__ import annotations

import os


LOCAL_APP_URL = "http://localhost:5173"
LOCAL_API_URL = "http://localhost:8000"
LOCAL_CORS_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]


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
