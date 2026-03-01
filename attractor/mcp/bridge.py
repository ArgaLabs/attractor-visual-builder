"""Bridge between MCP tool definitions and Attractor's Tool / ToolRegistry."""

from __future__ import annotations

from typing import Any

from attractor.agent.tools.registry import RegisteredTool, ToolRegistry
from attractor.llm.models import ToolDefinition
from attractor.llm.tools import Tool
from attractor.mcp.client import MCPClient, MCPTool


def mcp_tool_to_attractor(mcp_tool: MCPTool, client: MCPClient) -> Tool:
    """Wrap a single MCPTool as an Attractor Tool that the LLM can call.

    The returned Tool.execute is an async callable that routes through MCPClient.call_tool().
    """

    async def _execute(**kwargs: Any) -> str:
        return await client.call_tool(mcp_tool.name, kwargs)

    return Tool(
        name=mcp_tool.name,
        description=mcp_tool.description or f"Tool '{mcp_tool.name}' from MCP server '{mcp_tool.server_label}'",
        parameters=mcp_tool.input_schema,
        execute=_execute,
    )


def mcp_tool_to_registered(mcp_tool: MCPTool, client: MCPClient) -> RegisteredTool:
    """Wrap a MCPTool as a RegisteredTool for use in an agent ToolRegistry."""

    async def _executor(arguments: dict[str, Any], **_: Any) -> str:
        return await client.call_tool(mcp_tool.name, arguments)

    return RegisteredTool(
        definition=ToolDefinition(
            name=mcp_tool.name,
            description=mcp_tool.description or f"MCP tool from '{mcp_tool.server_label}'",
            parameters=mcp_tool.input_schema,
        ),
        executor=_executor,
    )


async def load_mcp_tools(client: MCPClient) -> list[Tool]:
    """Connect to an MCP server and return all its tools as Attractor Tool objects.

    These can be passed directly to generate():
        tools = await load_mcp_tools(client)
        result = await generate(model="claude-sonnet-4-5", prompt="...", tools=tools)
    """
    mcp_tools = await client.list_tools()
    return [mcp_tool_to_attractor(t, client) for t in mcp_tools]


async def register_mcp_server(registry: ToolRegistry, client: MCPClient) -> list[str]:
    """Discover all tools from an MCP server and register them in a ToolRegistry.

    Returns the list of registered tool names.

    Example:
        async with MCPClient.stdio("npx", "-y", "@modelcontextprotocol/server-filesystem", "/ws") as c:
            names = await register_mcp_server(registry, c)
            print(f"Registered MCP tools: {names}")
    """
    mcp_tools = await client.list_tools()
    names: list[str] = []
    for mt in mcp_tools:
        registry.register(mcp_tool_to_registered(mt, client))
        names.append(mt.name)
    return names


class MCPSession:
    """Manages a pool of connected MCP clients for a pipeline or agent session.

    Usage:
        session = MCPSession()
        await session.add_stdio("filesystem", "npx", "-y", "@modelcontextprotocol/server-filesystem", "/ws")
        await session.add_http("browser", "http://localhost:3001")

        # Get all tools as Attractor Tool objects for generate()
        tools = await session.all_tools()

        # Or register into an agent ToolRegistry
        await session.register_all(registry)

        # Always close when done
        await session.close()
    """

    def __init__(self) -> None:
        self._clients: list[MCPClient] = []

    async def add_stdio(self, label: str, cmd: str, *args: str, env: dict[str, str] | None = None) -> MCPClient:
        """Add and connect a stdio MCP server."""
        client = MCPClient.stdio(cmd, *args, label=label, env=env)
        await client.__aenter__()
        self._clients.append(client)
        return client

    async def add_http(self, label: str, base_url: str, headers: dict[str, str] | None = None) -> MCPClient:
        """Add and connect an HTTP MCP server."""
        client = MCPClient.http(base_url, label=label, headers=headers)
        await client.__aenter__()
        self._clients.append(client)
        return client

    async def all_tools(self) -> list[Tool]:
        """Return all tools from all connected MCP servers as Attractor Tool objects."""
        tools: list[Tool] = []
        for client in self._clients:
            tools.extend(await load_mcp_tools(client))
        return tools

    async def register_all(self, registry: ToolRegistry) -> dict[str, list[str]]:
        """Register all MCP tools from all servers into a ToolRegistry.

        Returns a dict mapping server label → list of registered tool names.
        """
        result: dict[str, list[str]] = {}
        for client in self._clients:
            names = await register_mcp_server(registry, client)
            result[client.label] = names
        return result

    async def close(self) -> None:
        for client in self._clients:
            await client.__aexit__(None, None, None)
        self._clients.clear()

    async def __aenter__(self) -> "MCPSession":
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()
