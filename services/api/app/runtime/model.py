"""Canonical model-provider boundary for runtime-owned agents.

The implementation lives in :mod:`app.runtime.model_impl`.  This module is
the stable import surface for API, Worker and Pi bridge code; the historical
``app.agent.llm`` module re-exports it only for old tests and replay fixtures.
"""

from __future__ import annotations

from typing import Any

from . import model_impl as _provider_impl


def __getattr__(name: str) -> Any:
    return getattr(_provider_impl, name)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(dir(_provider_impl)))


__all__ = [name for name in dir(_provider_impl) if not name.startswith("__")]
