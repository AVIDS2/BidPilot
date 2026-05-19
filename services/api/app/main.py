from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

import os
import uuid
import time
import structlog
import traceback

logger = structlog.get_logger()
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.audit.router import router as audit_router
from app.auth.router import router as auth_router
from app.auth.service import require_admin, require_auth
from app.bundles.router import router as bundles_router
from app.deliverables.router import router as deliverables_router
from app.documents.router import router as documents_router
from app.drafting.router import router as drafting_router
from app.evidence.router import router as evidence_router
from app.execution.router import router as execution_router
from app.ops.router import router as ops_router
from app.projects.router import router as projects_router
from app.requirements.router import router as requirements_router
from app.retrieval.router import router as retrieval_router
from app.review.router import router as review_router
from app.scenarios.router import router as scenarios_router
from app.parsed_assets.router import router as parsed_assets_router
from app.versions.router import router as versions_router
from app.export.router import router as export_router
from app.billing.router import router as billing_router
from app.teams.router import router as teams_router
from app.organizations.router import router as organizations_router
from app.invitations.router import router as invitations_router
from app.logging import setup_logging

setup_logging()

class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())[:8]
        structlog.contextvars.bind_contextvars(request_id=request_id)
        start = time.time()
        response = await call_next(request)
        duration_ms = int((time.time() - start) * 1000)
        logger.info("request", method=request.method, path=request.url.path, status=response.status_code, duration_ms=duration_ms)
        return response


app = FastAPI(title="DocPilot API")

app.add_middleware(RequestContextMiddleware)

rate_limit = os.environ.get("DOCPILOT_RATE_LIMIT", "60/minute")
limiter = Limiter(key_func=get_remote_address, default_limits=[rate_limit])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Standardized error format with backward-compatible 'detail' key."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": f"http_{exc.status_code}",
            "message": exc.detail if isinstance(exc.detail, str) else "Request error",
            "detail": exc.detail,
            "details": exc.detail if not isinstance(exc.detail, str) else None,
        },
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(
        status_code=400,
        content={
            "error": "bad_request",
            "message": str(exc),
            "detail": str(exc),
            "details": None,
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception", path=request.url.path, method=request.method)
    return JSONResponse(
        status_code=500,
        content={"error": "internal_error", "message": "An internal error occurred", "details": None},
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Public routes (no auth required)
app.include_router(auth_router)
app.include_router(scenarios_router)

# Protected routes (auth enforced when DOCPILOT_AUTH_REQUIRED=true)
_protected = [Depends(require_auth)]
app.include_router(projects_router, dependencies=_protected)
app.include_router(bundles_router, dependencies=_protected)
app.include_router(deliverables_router, dependencies=_protected)
app.include_router(documents_router, dependencies=_protected)
app.include_router(drafting_router, dependencies=_protected)
app.include_router(evidence_router, dependencies=_protected)
app.include_router(execution_router, dependencies=_protected)
app.include_router(requirements_router, dependencies=_protected)
app.include_router(retrieval_router, dependencies=_protected)
app.include_router(review_router, dependencies=_protected)
app.include_router(audit_router, dependencies=[Depends(require_admin)])
app.include_router(ops_router, dependencies=[Depends(require_admin)])
app.include_router(parsed_assets_router, dependencies=_protected)
app.include_router(versions_router, dependencies=_protected)
app.include_router(export_router, dependencies=_protected)
app.include_router(teams_router, dependencies=_protected)
app.include_router(organizations_router, dependencies=_protected)
app.include_router(invitations_router, dependencies=_protected)
app.include_router(billing_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
