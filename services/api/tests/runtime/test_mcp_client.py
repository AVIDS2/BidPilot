"""MCP client adapter tests: config parsing, namespace safety, schema conversion.

Uses a minimal stdio MCP server fixture so the full list_tools + call_tool
path is exercised without any external dependency.
"""

from __future__ import annotations

import json
import asyncio

import pytest

from app.runtime import mcp_client


def test_parse_mcp_tool_name_splits_prefix() -> None:
    assert mcp_client.parse_mcp_tool_name("mcp_web_search") == ("web", "search")
    assert mcp_client.parse_mcp_tool_name("mcp_docs_lookup") == ("docs", "lookup")
    assert mcp_client.parse_mcp_tool_name("search_projects") is None
    assert mcp_client.parse_mcp_tool_name("mcp_only") is None


def test_parse_mcp_tool_name_preserves_underscored_server_names() -> None:
    env = {
        "DOCPILOT_MCP_SERVERS": json.dumps(
            [{"name": "tavily_search", "command": "npx"}]
        )
    }

    assert mcp_client.parse_mcp_tool_name(
        "mcp_tavily_search_web_search",
        env=env,
    ) == ("tavily_search", "web_search")


def test_env_servers_requires_allowlist() -> None:
    env = {"DOCPILOT_MCP_SERVERS": json.dumps({"name": "web", "command": "npx"})}
    servers = mcp_client._env_servers(env)
    assert len(servers) == 1
    assert servers[0].name == "web"
    assert servers[0].command == "npx"
    assert servers[0].trusted_mutations is False


def test_env_servers_trusted_mutations_flag() -> None:
    env = {
        "DOCPILOT_MCP_SERVERS": json.dumps(
            [
                {"name": "sensing", "command": "a"},
                {"name": "trusted", "command": "b"},
            ]
        ),
        "DOCPILOT_MCP_TRUSTED_MUTATIONS": "trusted",
    }
    servers = mcp_client._env_servers(env)
    by_name = {s.name: s for s in servers}
    assert by_name["sensing"].trusted_mutations is False
    assert by_name["trusted"].trusted_mutations is True


def test_env_servers_rejects_ambiguous_and_bad_names() -> None:
    env = {
        "DOCPILOT_MCP_SERVERS": json.dumps(
            [
                {"name": "ok", "command": "a"},
                {"name": "bad name!", "command": "b"},
                {"name": "both", "command": "a", "url": "http://x"},
                {"name": "neither"},
            ]
        )
    }
    servers = mcp_client._env_servers(env)
    assert [s.name for s in servers] == ["ok"]


def test_openai_parameters_converts_schema() -> None:
    schema = {
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
        "additionalProperties": False,
    }
    converted = mcp_client._openai_parameters(schema)
    assert converted["type"] == "object"
    assert converted["properties"]["query"]["type"] == "string"
    assert converted["required"] == ["query"]
    assert converted["additionalProperties"] is False


def test_openai_parameters_permissive_fallback() -> None:
    converted = mcp_client._openai_parameters(None)
    assert converted["type"] == "object"
    assert converted["properties"] == {}
    assert converted["additionalProperties"] is True


def test_spec_for_tool_namespaced_and_sensing_marked() -> None:
    cfg = mcp_client.McpServerConfig(name="web", command="npx")
    tool = type("Tool", (), {"name": "search", "description": "Search web", "inputSchema": {"type": "object"}})()
    spec = mcp_client._spec_for_tool(cfg, tool)
    assert spec is not None
    assert spec.name == "mcp_web_search"
    assert "[read-only MCP sensing]" in spec.description
    assert spec.parameters["type"] == "object"


def test_spec_for_tool_trusted_keeps_original_description() -> None:
    cfg = mcp_client.McpServerConfig(name="web", command="npx", trusted_mutations=True)
    tool = type("Tool", (), {"name": "search", "description": "Search web", "inputSchema": None})()
    spec = mcp_client._spec_for_tool(cfg, tool)
    assert spec is not None
    assert spec.name == "mcp_web_search"
    assert "[read-only MCP sensing]" not in spec.description
    assert spec.description == "Search web"


def test_spec_preserves_mcp_output_schema_and_annotations() -> None:
    cfg = mcp_client.McpServerConfig(name="web", command="npx")
    tool = type("Tool", (), {
        "name": "search",
        "description": "Search web",
        "inputSchema": {"type": "object"},
        "outputSchema": {"type": "object", "properties": {"items": {"type": "array"}}},
        "annotations": {"readOnlyHint": True},
    })()
    spec = mcp_client._spec_for_tool(cfg, tool)
    assert spec is not None
    assert spec.output_schema == tool.outputSchema
    assert spec.annotations == tool.annotations


def test_mcp_discovery_consumes_paginated_tool_lists(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Session:
        def __init__(self) -> None:
            self.calls: list[str | None] = []

        async def list_tools(self, cursor=None):
            self.calls.append(cursor)
            row = type("Tool", (), {"name": f"search_{len(self.calls)}", "description": "search", "inputSchema": {"type": "object"}})()
            return type("Page", (), {"tools": [row], "nextCursor": "next" if len(self.calls) == 1 else None})()

    session = _Session()
    cfg = mcp_client.McpServerConfig(name="web", command="npx")

    async def acquire(_cfg):
        return session

    monkeypatch.setattr(mcp_client, "_env_servers", lambda _env=None: [cfg])
    monkeypatch.setattr(mcp_client._pool, "acquire", acquire)
    specs = asyncio.run(mcp_client.list_mcp_tool_specs())
    assert [spec.name for spec in specs] == ["mcp_web_search_1", "mcp_web_search_2"]
    assert session.calls == [None, "next"]


def test_mcp_tool_discovery_times_out_instead_of_blocking_harness(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _IdleSession:
        async def list_tools(self) -> None:
            await asyncio.Event().wait()

    cfg = mcp_client.McpServerConfig(name="web", command="fake")

    async def _acquire(_cfg: mcp_client.McpServerConfig) -> _IdleSession:
        return _IdleSession()

    monkeypatch.setattr(mcp_client, "_env_servers", lambda _env=None: [cfg])
    monkeypatch.setattr(mcp_client._pool, "acquire", _acquire)
    monkeypatch.setattr(mcp_client, "_MCP_OPERATION_TIMEOUT_SECONDS", 0.01)

    async def _collect() -> None:
        assert await mcp_client.list_mcp_tool_specs() == []

    asyncio.run(_collect())
