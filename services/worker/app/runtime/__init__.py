"""Worker-side adapters for product runtime observability."""

from __future__ import annotations

from pathlib import Path


_api_runtime_path = Path(__file__).resolve().parents[3] / "api" / "app" / "runtime"
if _api_runtime_path.is_dir():
    __path__.append(str(_api_runtime_path))
