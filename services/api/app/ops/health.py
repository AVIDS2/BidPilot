"""Safe dependency health checks shared by public readiness and admin ops."""

from __future__ import annotations

import os

import structlog
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = structlog.get_logger()


def collect_dependency_checks(db: Session, *, include_worker: bool = False) -> dict[str, str]:
    """Return only safe dependency states; never surface backend exception text."""
    checks: dict[str, str] = {}

    try:
        db.scalar(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception:
        logger.warning("dependency_health_check_failed", dependency="postgres")
        checks["postgres"] = "unavailable"

    try:
        import redis as redis_lib

        redis_url = os.environ.get("DOCPILOT_REDIS_URL", "redis://localhost:6379/0")
        redis_lib.from_url(redis_url).ping()
        checks["redis"] = "ok"
    except Exception:
        logger.warning("dependency_health_check_failed", dependency="redis")
        checks["redis"] = "unavailable"

    try:
        from app.adapters.storage import _get_client

        _get_client().list_buckets()
        checks["minio"] = "ok"
    except Exception:
        logger.warning("dependency_health_check_failed", dependency="minio")
        checks["minio"] = "unavailable"

    if include_worker:
        try:
            from celery import Celery

            redis_url = os.environ.get("DOCPILOT_REDIS_URL", "redis://localhost:6379/0")
            worker_stats = Celery("docpilot-check", broker=redis_url).control.inspect().stats()
            checks["worker"] = "ok" if worker_stats else "degraded"
        except Exception:
            logger.warning("dependency_health_check_failed", dependency="worker")
            checks["worker"] = "unavailable"

    return checks


def dependencies_are_ready(checks: dict[str, str]) -> bool:
    return all(status == "ok" for status in checks.values())
