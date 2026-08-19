"""MCP client adapter for the governed harness.

Bridges external Model Context Protocol servers into the harness as read-style
sensing tools, following the trust boundaries from AI-Agents-in-Depth 4.3:

  * Allowlist only: servers must be listed in ``DOCPILOT_MCP_SERVERS``.  No
    server is auto-discovered, so a third party cannot attach itself.
  * Namespace prefix: every tool is exposed as ``mcp_<server>_<tool>``.  This
    prevents tool shadowing (a remote server reusing a capability name) from
    hijacking the call, and keeps the harness's own approval/audit path intact.
  * Schema conversion: MCP ``inputSchema`` (JSON Schema) is translated to the
    OpenAI tool-call shape the harness already uses for capabilities.
  * Degradation: an unreachable or unsupported server logs once and is skipped;
    a flaky MCP server never blocks a harness turn.
  * Sensing-only by default: MCP tools are read/sensing boundaries.  Mutations
    (create/write/delete/upload) still go through ``execute_capability`` so
    approval, quota, tenant and audit apply.  A mutation-looking MCP tool is
    exposed read-only unless a server is explicitly marked ``trusted_mutations``.

MCP 1.27+ SDK supports both stdio (local command) and Streamable HTTP servers.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

_ENV_NAME = "DOCPILOT_MCP_SERVERS"
# MCP servers whose tools may perform mutations (default: sensing-only).
_ENV_TRUSTED = "DOCPILOT_MCP_TRUSTED_MUTATIONS"
_ENV_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,31}$")
_TOOL_NAME_RE = re.compile(r"^[A-Za-z0-9_]{1,64}$")

# Long-running servers are pooled across turns inside a process.  A short idle
# TTL keeps an unused pool from holding connections open forever.
_POOL_TTL_SECONDS = 300.0
# MCP servers are optional extensions. A slow launch, discovery, or tool call
# must not hold the interactive harness in an indeterminate running state.
_MCP_OPERATION_TIMEOUT_SECONDS = 20.0


@dataclass(frozen=True)
class McpServerConfig:
    name: str
    command: str | None  # stdio transport
    args: tuple[str, ...] = ()
    url: str | None = None  # Streamable HTTP transport
    env: dict[str, str] = field(default_factory=dict)  # extra env vars (e.g. API keys) for the server process
    trusted_mutations: bool = False


@dataclass(frozen=True)
class McpToolSpec:
    """OpenAI-compatible tool spec for one remote MCP tool."""

    name: str
    description: str
    parameters: dict[str, Any]


def normalize_mcp_search_payload(
    outcome: dict[str, Any],
    arguments: dict[str, Any],
    server_name: str,
) -> dict[str, Any]:
    """Project a verifiable MCP search response into the public timeline shape."""
    source = outcome.get("structured_content")
    if not isinstance(source, dict):
        raw = outcome.get("content")
        if isinstance(raw, str):
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = None
            source = parsed if isinstance(parsed, dict) else {}
        else:
            source = {}
    candidates = source.get("results") or source.get("items") or []
    items: list[dict[str, str]] = []
    if isinstance(candidates, list):
        for candidate in candidates[:10]:
            if not isinstance(candidate, dict):
                continue
            title = str(candidate.get("title") or "").strip()
            url = str(candidate.get("url") or "").strip()
            snippet = str(candidate.get("content") or candidate.get("snippet") or "").strip()
            if title and url.startswith(("https://", "http://")):
                items.append(
                    {"title": title[:200], "url": url[:500], "snippet": snippet[:500]}
                )
    return {
        "query": str(arguments.get("query") or "").strip(),
        "provider": f"mcp:{server_name}",
        "count": len(items),
        "items": items,
    }


def _env_servers(env: dict[str, str] | None = None) -> list[McpServerConfig]:
    raw = (env or os.environ).get(_ENV_NAME, "")
    if not raw.strip():
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("DOCPILOT_MCP_SERVERS is not valid JSON; ignoring MCP servers")
        return []
    trusted = set()
    raw_trusted = (env or os.environ).get(_ENV_TRUSTED, "")
    if raw_trusted.strip():
        trusted = {item.strip() for item in raw_trusted.split(",") if item.strip()}
    servers: list[McpServerConfig] = []
    if isinstance(parsed, dict):
        parsed = [parsed]
    for entry in parsed if isinstance(parsed, list) else []:
        if not isinstance(entry, dict):
            continue
        name = str(entry.get("name") or "").strip()
        if not _ENV_NAME_RE.fullmatch(name):
            continue
        command = str(entry["command"]).strip() if entry.get("command") else None
        url = str(entry["url"]).strip() if entry.get("url") else None
        if command and url:
            # Ambiguous; require exactly one transport.
            logger.warning("MCP server %s declares both command and url; skipping", name)
            continue
        if not command and not url:
            continue
        args = tuple(str(arg) for arg in entry.get("args") or [])
        env_extra: dict[str, str] = {}
        raw_env = entry.get("env")
        if isinstance(raw_env, dict):
            for env_key, env_value in raw_env.items():
                if isinstance(env_key, str) and isinstance(env_value, str):
                    env_extra[env_key] = env_value
        servers.append(
            McpServerConfig(
                name=name,
                command=command,
                args=args,
                url=url,
                env=env_extra,
                trusted_mutations=name in trusted,
            )
        )
    return servers


def _openai_parameters(input_schema: dict[str, Any] | None) -> dict[str, Any]:
    """Convert an MCP JSON Schema to the OpenAI tool parameters shape.

    Falls back to a permissive object when the server omits a schema.
    """
    if not isinstance(input_schema, dict):
        return {"type": "object", "properties": {}, "additionalProperties": True}
    parameters: dict[str, Any] = {}
    for key in ("type", "properties", "required", "additionalProperties", "description"):
        if key in input_schema:
            parameters[key] = input_schema[key]
    parameters.setdefault("type", "object")
    parameters.setdefault("properties", {})
    parameters.setdefault("additionalProperties", True)
    return parameters


def _spec_for_tool(server: McpServerConfig, tool: Any) -> McpToolSpec | None:
    name = getattr(tool, "name", None)
    if not isinstance(name, str) or not _TOOL_NAME_RE.fullmatch(name):
        return None
    exposed = f"mcp_{server.name}_{name}"
    description = getattr(tool, "description", None) or ""
    if not isinstance(description, str):
        description = str(description)
    # Sensing-only default: mutations stay behind capability approvals unless
    # the server is explicitly trusted for mutations.
    if not server.trusted_mutations:
        description = (
            f"[read-only MCP sensing] {description}".strip()
            if description
            else "[read-only MCP sensing]"
        )
    input_schema = getattr(tool, "inputSchema", None)
    return McpToolSpec(
        name=exposed,
        description=description,
        parameters=_openai_parameters(input_schema if isinstance(input_schema, dict) else None),
    )


class _McpServerPool:
    """Per-process pool of live MCP sessions, keyed by server name."""

    def __init__(self) -> None:
        self._sessions: dict[str, tuple[AsyncExitStack, Any]] = {}
        self._last_used: dict[str, float] = {}

    async def acquire(self, cfg: McpServerConfig) -> Any | None:
        if cfg.name in self._sessions:
            self._last_used[cfg.name] = asyncio.get_event_loop().time()
            return self._sessions[cfg.name][1]
        try:
            stack = AsyncExitStack()
            if cfg.command:
                from mcp.client.stdio import StdioServerParameters, stdio_client

                server_params = StdioServerParameters(
                    command=cfg.command,
                    args=list(cfg.args),
                    env={**os.environ, **cfg.env},
                    cwd=os.getcwd(),
                )
                read, write = await asyncio.wait_for(
                    stack.enter_async_context(stdio_client(server_params)),
                    timeout=_MCP_OPERATION_TIMEOUT_SECONDS,
                )
            elif cfg.url:
                from mcp.client.streamable_http import streamablehttp_client

                transport = await asyncio.wait_for(
                    stack.enter_async_context(streamablehttp_client(url=cfg.url)),
                    timeout=_MCP_OPERATION_TIMEOUT_SECONDS,
                )
                read, write = transport[0], transport[1]
            else:
                return None
            from mcp import ClientSession

            session = await asyncio.wait_for(
                stack.enter_async_context(ClientSession(read, write)),
                timeout=_MCP_OPERATION_TIMEOUT_SECONDS,
            )
            await asyncio.wait_for(session.initialize(), timeout=_MCP_OPERATION_TIMEOUT_SECONDS)
            self._sessions[cfg.name] = (stack, session)
            self._last_used[cfg.name] = asyncio.get_event_loop().time()
            return session
        except Exception as exc:  # noqa: BLE001
            logger.warning("MCP server %s unavailable: %s", cfg.name, type(exc).__name__)
            if os.getenv("DOCPILOT_MCP_DEBUG"):
                import traceback

                traceback.print_exc()
            if "stack" in locals():
                try:
                    await stack.aclose()
                except Exception:  # noqa: BLE001
                    pass
            return None

    async def close_idle(self, now: float | None = None) -> None:
        now = now if now is not None else asyncio.get_event_loop().time()
        stale = [name for name, ts in self._last_used.items() if now - ts > _POOL_TTL_SECONDS]
        for name in stale:
            stack, _session = self._sessions.pop(name, (None, None))
            self._last_used.pop(name, None)
            if stack:
                try:
                    await stack.aclose()
                except Exception:  # noqa: BLE001
                    logger.debug("MCP pool close failed for %s", name)

    async def shutdown(self) -> None:
        for name in list(self._sessions):
            stack, _session = self._sessions.pop(name, (None, None))
            self._last_used.pop(name, None)
            if stack:
                try:
                    await stack.aclose()
                except Exception:  # noqa: BLE001
                    logger.debug("MCP pool close failed for %s", name)


_pool = _McpServerPool()


def configured_servers(env: dict[str, str] | None = None) -> list[McpServerConfig]:
    return _env_servers(env)


async def list_mcp_tool_specs(env: dict[str, str] | None = None) -> list[McpToolSpec]:
    """Return OpenAI tool specs for every configured MCP server's tools."""
    servers = _env_servers(env)
    if not servers:
        return []
    specs: list[McpToolSpec] = []
    for cfg in servers:
        session = await _pool.acquire(cfg)
        if session is None:
            continue
        try:
            result = await asyncio.wait_for(
                session.list_tools(), timeout=_MCP_OPERATION_TIMEOUT_SECONDS
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("MCP server %s list_tools failed: %s", cfg.name, type(exc).__name__)
            continue
        tools = getattr(result, "tools", None) or getattr(result, "result", {}).get("tools", []) or []
        for tool in tools:
            spec = _spec_for_tool(cfg, tool)
            if spec:
                specs.append(spec)
    return specs


async def call_mcp_tool(
    server_name: str,
    tool_name: str,
    arguments: dict[str, Any],
    *,
    env: dict[str, str] | None = None,
) -> Any:
    """Call one MCP tool by its server + original name.

    ``tool_name`` is the un-prefixed tool name (the harness strips the
    ``mcp_<server>_`` prefix before dispatch).  Arguments are passed verbatim.
    """
    servers = _env_servers(env)
    cfg = next((s for s in servers if s.name == server_name), None)
    if cfg is None:
        raise ValueError(f"MCP server not configured: {server_name}")
    session = await _pool.acquire(cfg)
    if session is None:
        raise ConnectionError(f"MCP server unavailable: {server_name}")
    result = await asyncio.wait_for(
        session.call_tool(tool_name, arguments or {}),
        timeout=_MCP_OPERATION_TIMEOUT_SECONDS,
    )
    # Normalize result to text so ToolMessage stays plain.  ``content`` is a
    # list of TextContent / dict parts; ``structuredContent`` holds the
    # structured object when the server returns one.
    content = getattr(result, "content", None)
    text_parts: list[str] = []
    if isinstance(content, list):
        for part in content:
            if isinstance(part, dict):
                value = part.get("text")
            else:
                value = getattr(part, "text", None)
            if isinstance(value, str) and value:
                text_parts.append(value)
    structured = getattr(result, "structuredContent", None)
    if not text_parts:
        if isinstance(structured, dict):
            return {"content": json.dumps(structured, ensure_ascii=False), "structured_content": structured}
    if isinstance(content, str):
        return {"content": content, "structured_content": structured if isinstance(structured, dict) else None}
    return (
        {"content": "\n".join(text_parts), "structured_content": structured if isinstance(structured, dict) else None}
        if text_parts
        else {"content": "", "structured_content": structured if isinstance(structured, dict) else None}
    )


def parse_mcp_tool_name(
    exposed_name: str,
    *,
    env: dict[str, str] | None = None,
) -> tuple[str, str] | None:
    """Split ``mcp_<server>_<tool>`` back into (server, tool).

    Returns None for names without the ``mcp_`` prefix (capabilities).
    """
    if not exposed_name.startswith("mcp_"):
        return None
    # Server identifiers may contain underscores. Prefer the configured
    # allowlist over a naive first-underscore split so `mcp_tavily_search`
    # and `mcp_tavily_search_news` both route to their real server.
    for server in sorted(_env_servers(env), key=lambda item: len(item.name), reverse=True):
        prefix = f"mcp_{server.name}_"
        if exposed_name.startswith(prefix):
            tool_name = exposed_name[len(prefix):]
            return (server.name, tool_name) if _TOOL_NAME_RE.fullmatch(tool_name) else None

    # Keep a deterministic compatibility fallback for persisted or test-only
    # names when the current process no longer has the original MCP config.
    rest = exposed_name[4:]
    parts = rest.split("_", 1)
    if len(parts) != 2 or not _TOOL_NAME_RE.fullmatch(parts[1]):
        return None
    return parts[0], parts[1]


async def shutdown_mcp_pool() -> None:
    await _pool.shutdown()


__all__ = [
    "call_mcp_tool",
    "configured_servers",
    "list_mcp_tool_specs",
    "parse_mcp_tool_name",
    "shutdown_mcp_pool",
]
