"""Compatibility exports for the retired ``app.agent`` namespace.

New code must import from ``app.runtime.model``.  Keeping this thin shim
preserves historical test and replay imports while the provider implementation
has a single canonical home under the runtime boundary.
"""

import app.runtime.model as _runtime_model

from app.runtime.model import *  # noqa: F403,F401

__all__ = _runtime_model.__all__
