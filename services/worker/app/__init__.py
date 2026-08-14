"""Worker application package.

The worker owns the execution graph and Celery entry points. A small set of
domain services (radar polling and outbound webhooks) live with the API so
their command/query behavior has one source of truth. Extend this package's
module search path to expose those services without copying their code into
the worker package.
"""

from __future__ import annotations

from pathlib import Path


_api_app_path = Path(__file__).resolve().parents[2] / "api" / "app"
if _api_app_path.is_dir():
    __path__.append(str(_api_app_path))
