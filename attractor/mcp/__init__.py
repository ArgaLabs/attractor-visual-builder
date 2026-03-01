"""MCP (Model Context Protocol) integration for Attractor.

Quick start — use tools from an MCP server in a pipeline:

    from attractor.mcp import MCPClient, MCPSession
    from attractor.pipeline.engine import create_default_registry, run

    async with MCPSession() as mcp:
        await mcp.add_stdio("fs", "npx", "-y", "@modelcontextprotocol/server-filesystem", "/workspace")
        registry = create_default_registry(backend=my_backend, mcp_session=mcp)
        result = await run(graph, registry=registry)

Quick start — use MCP tools directly in generate():

    from attractor.mcp import MCPClient, load_mcp_tools
    from attractor.llm.generate import generate

    async with MCPClient.stdio("npx", "-y", "@modelcontextprotocol/server-filesystem", "/ws") as c:
        tools = await load_mcp_tools(c)
        result = await generate(model="claude-sonnet-4-5", prompt="List files in /ws", tools=tools)
"""

from attractor.mcp.bridge import MCPSession, load_mcp_tools, register_mcp_server
from attractor.mcp.client import MCPClient, MCPTool

__all__ = [
    "MCPClient",
    "MCPTool",
    "MCPSession",
    "load_mcp_tools",
    "register_mcp_server",
]
