from __future__ import annotations

import asyncio

from app.runtime import pi_config
from app.runtime.mcp_client import McpToolSpec


def test_pi_tools_for_run_exposes_configured_mcp_tools_as_parallel_resources(monkeypatch) -> None:
    async def fake_specs() -> list[McpToolSpec]:
        return [
            McpToolSpec(
                name="mcp_tavily_search",
                description="Search public sources",
                parameters={"type": "object", "properties": {"query": {"type": "string"}}},
                server_name="tavily",
                tool_name="search",
            )
        ]

    monkeypatch.setattr(pi_config, "list_mcp_tool_specs", fake_specs)

    tools = asyncio.run(pi_config.pi_tools_for_run())
    mcp_tool = next(tool for tool in tools if tool["name"] == "mcp_tavily_search")

    assert mcp_tool["resourceKind"] == "mcp"
    assert mcp_tool["provider"] == "tavily"
    assert mcp_tool["executionMode"] == "parallel"
