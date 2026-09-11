"""Mem0 Platform adapter for low-risk, user-scoped profile memory.

Mem0 is deliberately kept at the personalization edge. BidPilot's
PostgreSQL memory records remain the source of truth for project facts,
evidence, approvals, and procurement requirements.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import hashlib
import logging
import os
from typing import Any, Mapping, Sequence

import httpx
from mem0 import MemoryClient
from mem0.client.types import AddMemoryOptions, SearchMemoryOptions


logger = logging.getLogger(__name__)

_DEFAULT_HOST = "https://api.mem0.ai"
_DEFAULT_AGENT_ID = "bidpilot-assistant"
_DEFAULT_TIMEOUT_SECONDS = 1.5
_MAX_QUERY_CHARACTERS = 1_200
_MAX_MESSAGE_CHARACTERS = 4_000
_PROFILE_INSTRUCTIONS = (
    "Only retain stable, low-risk personalization facts: language, response format, "
    "communication preferences, work style, and explicitly stated assistant preferences. "
    "Do not retain passwords, API keys, tokens, raw files, tender contents, tender deadlines, "
    "budgets, qualifications, legal claims, project facts, hidden reasoning, or tool payloads. "
    "Do not infer a preference from one accidental request."
)


@dataclass(frozen=True)
class Mem0ProfileMemory:
    """A safe subset of a Mem0 search result for prompt assembly."""

    memory_id: str
    text: str
    score: float | None
    categories: tuple[str, ...]

    def to_context_record(self) -> dict[str, Any]:
        return {
            "kind": "user_profile_memory",
            "scope": "user_private",
            "title": "用户长期偏好",
            "body_markdown": self.text,
            "memory_id": self.memory_id,
            "score": self.score,
            "categories": list(self.categories),
            "source": "mem0_platform",
        }


def mem0_enabled() -> bool:
    """Return true only when the deployment explicitly opts into Mem0."""

    return (
        os.getenv("DOCPILOT_MEM0_ENABLED", "false").strip().lower() in {"1", "true", "yes"}
        and bool(os.getenv("DOCPILOT_MEM0_API_KEY", "").strip() or os.getenv("MEM0_API_KEY", "").strip())
    )


def mem0_agent_id(user_id: str | None = None) -> str:
    """Return a user-isolated assistant entity id.

    A shared agent id would make assistant-extracted memories from one member
    visible to every other member in the same organization. The user entity
    remains the private scope; the suffix keeps the assistant entity private
    too while preserving a stable base for operational filtering.
    """
    base = os.getenv("DOCPILOT_MEM0_AGENT_ID", _DEFAULT_AGENT_ID).strip() or _DEFAULT_AGENT_ID
    return f"{base}:{user_id}" if user_id else base


def mem0_host() -> str:
    return os.getenv("DOCPILOT_MEM0_HOST", _DEFAULT_HOST).strip().rstrip("/") or _DEFAULT_HOST


def mem0_timeout_seconds() -> float:
    try:
        value = float(os.getenv("DOCPILOT_MEM0_TIMEOUT_SECONDS", str(_DEFAULT_TIMEOUT_SECONDS)))
    except ValueError:
        value = _DEFAULT_TIMEOUT_SECONDS
    return min(max(value, 0.2), 5.0)


def mem0_profile_fingerprint(*, user_id: str, org_id: str, run_id: str, messages: Sequence[Mapping[str, str]]) -> str:
    """Return a stable local idempotency key without storing message text."""

    normalized = "|".join(
        f"{item.get('role', '')}:{item.get('content', '')[:_MAX_MESSAGE_CHARACTERS]}"
        for item in messages
    )
    return hashlib.sha256(f"mem0-profile-v1|{user_id}|{org_id}|{run_id}|{normalized}".encode()).hexdigest()


@lru_cache(maxsize=1)
def _client(api_key: str, host: str, timeout_seconds: float) -> MemoryClient:
    timeout = httpx.Timeout(timeout_seconds, connect=min(timeout_seconds, 2.0))
    http_client = httpx.Client(timeout=timeout)
    return MemoryClient(api_key=api_key, host=host, client=http_client)


def _configured_client() -> MemoryClient | None:
    if not mem0_enabled():
        return None
    api_key = (os.getenv("DOCPILOT_MEM0_API_KEY", "").strip() or os.getenv("MEM0_API_KEY", "").strip())
    try:
        return _client(api_key, mem0_host(), mem0_timeout_seconds())
    except Exception:  # noqa: BLE001 - optional provider must fail open
        logger.warning("Mem0 client initialization failed; continuing without profile memory", exc_info=True)
        return None


def _scope_filters(*, user_id: str, org_id: str) -> dict[str, Any]:
    # Mem0 stores facts extracted from user and assistant messages under
    # separate entities. Combining user_id and agent_id in one AND filter
    # therefore returns no results. Keep the tenant boundary as AND and query
    # the two entity scopes with OR, as documented by the official API.
    entity_filter: dict[str, Any] = {
        "OR": [
            {"user_id": user_id},
            {"agent_id": mem0_agent_id(user_id)},
        ]
    }
    # Mem0 Platform supports app_id for tenant/project separation. OSS
    # deployments can turn this off because their API does not expose app_id.
    if os.getenv("DOCPILOT_MEM0_APP_SCOPE", "true").strip().lower() in {"1", "true", "yes"}:
        return {"AND": [{"app_id": org_id}], "OR": entity_filter["OR"]}
    return entity_filter


def _entity_scope_kwargs(*, user_id: str | None = None, org_id: str | None = None) -> dict[str, str]:
    """Build SDK entity kwargs without sending Platform-only app_id to OSS hosts."""

    values: dict[str, str] = {}
    if user_id:
        values["user_id"] = user_id
    if org_id and os.getenv("DOCPILOT_MEM0_APP_SCOPE", "true").strip().lower() in {"1", "true", "yes"}:
        values["app_id"] = org_id
    return values


def search_profile_memory(
    *,
    user_id: str,
    org_id: str,
    query: str,
    top_k: int = 4,
) -> list[Mem0ProfileMemory]:
    """Search only the current user's BidPilot profile memories.

    This is an optional read path. Any provider, auth, quota, or network
    failure returns an empty list so a user never loses the primary Agent turn.
    """

    client = _configured_client()
    query_value = query.strip()[:_MAX_QUERY_CHARACTERS]
    if client is None or not query_value:
        return []
    try:
        response = client.search(
            query_value,
            options=SearchMemoryOptions(
                filters=_scope_filters(user_id=user_id, org_id=org_id),
                top_k=max(1, min(top_k, 8)),
                latest_only=True,
            ),
        )
    except Exception:  # noqa: BLE001 - profile memory is fail-open
        logger.warning("Mem0 profile search failed; continuing without profile memory", exc_info=True)
        return []
    rows = response.get("results", []) if isinstance(response, dict) else []
    if not isinstance(rows, list):
        return []
    return _profile_memories_from_rows(rows)


def _profile_memories_from_rows(rows: object) -> list[Mem0ProfileMemory]:
    if not isinstance(rows, list):
        return []
    memories: list[Mem0ProfileMemory] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        text = str(row.get("memory") or row.get("text") or "").strip()
        memory_id = str(row.get("id") or "").strip()
        if not text or not memory_id:
            continue
        raw_score = row.get("score")
        score = float(raw_score) if isinstance(raw_score, (int, float)) else None
        categories_value = row.get("categories")
        categories = tuple(str(item) for item in categories_value if item) if isinstance(categories_value, list) else ()
        memories.append(Mem0ProfileMemory(memory_id=memory_id, text=text[:_MAX_MESSAGE_CHARACTERS], score=score, categories=categories))
    return memories


def list_profile_memory(*, user_id: str, org_id: str) -> list[Mem0ProfileMemory]:
    """List the current user's bounded personal profile memories."""

    client = _configured_client()
    if client is None:
        return []
    try:
        response = client.get_all(
            filters=_scope_filters(user_id=user_id, org_id=org_id),
            page=1,
            page_size=50,
        )
    except Exception:  # noqa: BLE001 - profile memory is optional
        logger.warning("Mem0 profile listing failed; continuing without profile memory", exc_info=True)
        return []
    rows = response.get("results", []) if isinstance(response, dict) else []
    return _profile_memories_from_rows(rows)


def capture_profile_memory(
    *,
    user_id: str,
    org_id: str,
    run_id: str,
    messages: Sequence[Mapping[str, str]],
) -> dict[str, Any]:
    """Queue a low-risk profile extraction through the official SDK.

    The caller is a background task. The response is intentionally reduced to
    provider status and event id; message text and provider payloads are never
    written to logs or runtime events.
    """

    client = _configured_client()
    if client is None:
        return {"status": "disabled"}
    bounded_messages = [
        {"role": str(item.get("role") or "user"), "content": str(item.get("content") or "")[:_MAX_MESSAGE_CHARACTERS]}
        for item in messages
        if str(item.get("content") or "").strip()
    ]
    if not bounded_messages:
        return {"status": "skipped", "reason": "empty_messages"}
    try:
        scope_kwargs = _entity_scope_kwargs(user_id=user_id, org_id=org_id)
        response = client.add(
            bounded_messages,
            options=AddMemoryOptions(
                custom_instructions=_PROFILE_INSTRUCTIONS,
                metadata={"source": "bidpilot_assistant", "profile_version": "v1"},
            ),
            agent_id=mem0_agent_id(user_id),
            run_id=run_id,
            **scope_kwargs,
        )
    except Exception:  # noqa: BLE001 - profile capture cannot fail an Agent run
        logger.warning("Mem0 profile capture failed; assistant run remains successful", exc_info=True)
        return {"status": "failed"}
    event_id = response.get("event_id") if isinstance(response, dict) else None
    return {"status": "queued", "event_id": str(event_id) if event_id else None}


def delete_profile_memory(*, user_id: str, org_id: str) -> dict[str, Any]:
    """Delete one user's profile memories for one BidPilot organization."""

    client = _configured_client()
    if client is None:
        return {"status": "disabled"}
    try:
        # User and agent facts are separate records. Delete each scope in its
        # own request so account deletion cannot leave assistant-extracted
        # profile facts behind or rely on an impossible AND filter.
        app_scope = _entity_scope_kwargs(org_id=org_id)
        responses = [
            client.delete_all(user_id=user_id, **app_scope),
            client.delete_all(agent_id=mem0_agent_id(user_id), **app_scope),
        ]
    except Exception:  # noqa: BLE001 - deletion is retried by the caller
        logger.warning("Mem0 profile deletion failed", exc_info=True)
        return {"status": "failed"}
    return {
        "status": "deleted",
        "provider_response": [response if isinstance(response, dict) else {} for response in responses],
    }


def delete_profile_memory_item(*, memory_id: str) -> dict[str, Any]:
    """Delete one provider-side personal profile memory by id."""

    client = _configured_client()
    if client is None:
        return {"status": "disabled"}
    try:
        response = client.delete(memory_id=memory_id)
    except Exception:  # noqa: BLE001 - deletion is user-visible but fail-safe
        logger.warning("Mem0 profile memory deletion failed", exc_info=True)
        return {"status": "failed"}
    return {
        "status": "deleted",
        "provider_response": response if isinstance(response, dict) else {},
    }


def profile_context_records(memories: Sequence[Mem0ProfileMemory]) -> list[dict[str, Any]]:
    return [memory.to_context_record() for memory in memories]


__all__ = [
    "Mem0ProfileMemory",
    "capture_profile_memory",
    "delete_profile_memory",
    "delete_profile_memory_item",
    "list_profile_memory",
    "mem0_enabled",
    "mem0_profile_fingerprint",
    "profile_context_records",
    "search_profile_memory",
]
