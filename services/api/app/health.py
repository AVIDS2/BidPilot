"""Public liveness and safe readiness endpoints for deployment automation."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.ops.health import collect_dependency_checks, dependencies_are_ready

router = APIRouter(tags=["health"])


@router.get("/health/ready")
def readiness(db: Session = Depends(get_db)) -> JSONResponse:
    checks = collect_dependency_checks(db)
    is_ready = dependencies_are_ready(checks)
    return JSONResponse(
        status_code=200 if is_ready else 503,
        content={
            "status": "ready" if is_ready else "not_ready",
            "checks": checks,
        },
    )
