"""Security helpers for the worker service."""

from __future__ import annotations

from pathlib import Path


_api_security_path = Path(__file__).resolve().parents[3] / "api" / "app" / "security"
if _api_security_path.is_dir():
    __path__.append(str(_api_security_path))
