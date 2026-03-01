"""Tool registry for the coding agent."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

from pydantic import BaseModel

from attractor.llm.models import ToolDefinition

if TYPE_CHECKING:
    from attractor.mcp.client import MCPClient


class RegisteredTool(BaseModel):
    definition: ToolDefinition
    executor: Callable[..., Any] | None = None

    model_config = {"arbitrary_types_allowed": True}


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, RegisteredTool] = {}

    def register(self, tool: RegisteredTool) -> None:
        self._tools[tool.definition.name] = tool

    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)

    def get(self, name: str) -> RegisteredTool | None:
        return self._tools.get(name)

    def definitions(self) -> list[ToolDefinition]:
        return [t.definition for t in self._tools.values()]

    def names(self) -> list[str]:
        return list(self._tools.keys())

    async def mcp_connect(self, client: "MCPClient") -> list[str]:
        """Discover and register all tools from a connected MCP client.

        The client must already be initialised (i.e. used as an async context
        manager or manually awaited). Returns the list of registered tool names.

        Example:
            async with MCPClient.stdio("npx", "-y", "@modelcontextprotocol/server-filesystem", "/ws") as c:
                names = await registry.mcp_connect(c)
        """
        from attractor.mcp.bridge import register_mcp_server

        return await register_mcp_server(self, client)
