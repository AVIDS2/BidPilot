from pathlib import Path
from contextlib import asynccontextmanager
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

import uuid
import time
import structlog

logger = structlog.get_logger()

from app.audit.router import router as audit_router
from app.assistant.router import router as assistant_router
from app.auth.router import router as auth_router
from app.auth.service import require_admin, require_auth
from app.core.settings import get_cors_origin_regex, get_cors_origins
from app.bundles.router import router as bundles_router
from app.deliverables.router import router as deliverables_router
from app.documents.router import router as documents_router
from app.drafting.router import router as drafting_router
from app.evidence.router import router as evidence_router
from app.execution.router import router as execution_router
from app.ops.router import router as ops_router
from app.projects.router import router as projects_router
from app.requirements.router import router as requirements_router
from app.readiness.router import router as readiness_router
from app.retrieval.router import router as retrieval_router
from app.runtime.router import router as runtime_router
from app.review.router import router as review_router
from app.scenarios.router import router as scenarios_router
from app.parsed_assets.router import router as parsed_assets_router
from app.versions.router import router as versions_router
from app.export.router import router as export_router
from app.billing.router import router as billing_router
from app.teams.router import router as teams_router
from app.organizations.router import router as organizations_router
from app.chat.router import router as chat_router
from app.changes.router import router as changes_router
from app.collaboration.router import router as collaboration_router
from app.content_library.router import router as content_library_router
from app.opportunities.router import router as opportunities_router
from app.providers.router import router as providers_router
from app.response_plans.router import router as response_plans_router
from app.radar.router import router as radar_router
from app.webhooks.router import router as webhooks_router
from app.invitations.router import router as invitations_router
from app.usage.router import router as usage_router
from app.notifications.router import router as notifications_router
from app.memory.router import router as memory_router
from app.logging import setup_logging
from app.health import router as health_router
from app.security.api_rate_limiter import GlobalApiRateLimitMiddleware, create_api_rate_limiter

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


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    close_runtime_resources()


def close_runtime_resources() -> None:
    """Release all long-lived LangGraph checkpointer connections on shutdown."""
    from app.runtime.operator_graph import close_operator_checkpointer

    close_operator_checkpointer()


app = FastAPI(title="DocPilot API", lifespan=lifespan)

# The limiter is created during startup so production cannot silently fall
# back to per-process memory when Redis or trusted proxy configuration is bad.
api_rate_limiter = create_api_rate_limiter()
app.state.api_rate_limiter = api_rate_limiter
app.add_middleware(GlobalApiRateLimitMiddleware, limiter=api_rate_limiter)
app.add_middleware(RequestContextMiddleware)


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
    allow_origins=get_cors_origins(),
    allow_origin_regex=get_cors_origin_regex(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Public routes (no auth required)
app.include_router(health_router)
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
app.include_router(response_plans_router, dependencies=_protected)
app.include_router(readiness_router, dependencies=_protected)
app.include_router(memory_router, dependencies=_protected)
app.include_router(retrieval_router, dependencies=_protected)
app.include_router(review_router, dependencies=_protected)
app.include_router(audit_router, dependencies=[Depends(require_admin)])
app.include_router(ops_router, dependencies=[Depends(require_admin)])
app.include_router(parsed_assets_router, dependencies=_protected)
app.include_router(versions_router, dependencies=_protected)
app.include_router(export_router, dependencies=_protected)
app.include_router(teams_router, dependencies=_protected)
app.include_router(organizations_router, dependencies=_protected)
app.include_router(providers_router)
app.include_router(invitations_router, dependencies=_protected)
app.include_router(billing_router)
app.include_router(notifications_router, dependencies=_protected)
app.include_router(chat_router, dependencies=_protected)
app.include_router(opportunities_router, dependencies=_protected)
app.include_router(radar_router, dependencies=_protected)
app.include_router(webhooks_router, dependencies=_protected)
app.include_router(content_library_router, dependencies=_protected)
app.include_router(changes_router, dependencies=_protected)
app.include_router(collaboration_router, dependencies=_protected)
app.include_router(assistant_router, dependencies=_protected)
app.include_router(usage_router, dependencies=_protected)
app.include_router(runtime_router, dependencies=_protected)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
