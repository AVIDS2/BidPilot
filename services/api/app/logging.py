"""Structured logging configuration for DocPilot API."""

import logging
import os
import sys

import structlog


def setup_logging(level: str | None = None) -> None:
    """Configure structlog for JSON-structured output.

    Skips configuration if DOCPILOT_LOGGING=off (useful for tests).
    """
    if os.environ.get("DOCPILOT_LOGGING", "on").lower() == "off":
        return

    level = level or os.environ.get("DOCPILOT_LOG_LEVEL", "INFO")

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, level.upper(), logging.INFO)),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)
