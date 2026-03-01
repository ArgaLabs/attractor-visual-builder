"""MCP (Model Context Protocol) async client.

Supports two transports:
  - StdioTransport  — spawns a local subprocess and communicates over stdin/stdout
  - HttpTransport   — communicates with a remote MCP server over HTTP (POST JSON-RPC)

Usage:
    async with MCPClient.stdio("npx", "-y", "@modelcontextprotocol/server-filesystem", "/tmp") as client:
        tools = await client.list_tools()
        result = await client.call_tool("read_file", {"path": "/tmp/hello.txt"})

    async with MCPClient.http("http://localhost:3001") as client:
        tools = await client.list_tools()
"""

from __future__ import annotations

import asyncio
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


# ── JSON-RPC helpers ────────────────────────────────────────────────────────

def _make_request(id: int, method: str, params: dict[str, Any] | None = None) -> bytes:
    payload: dict[str, Any] = {"jsonrpc": "2.0", "id": id, "method": method}
    if params is not None:
        payload["params"] = params
    return (json.dumps(payload) + "\n").encode()


def _parse_response(data: str) -> dict[str, Any]:
    return json.loads(data.strip())


# ── Tool model ───────────────────────────────────────────────────────────────

@dataclass
class MCPTool:
    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)
    server_label: str = ""

    @classmethod
    def from_mcp_dict(cls, d: dict[str, Any], server_label: str = "") -> "MCPTool":
        return cls(
            name=d["name"],
            description=d.get("description", ""),
            input_schema=d.get("inputSchema", {"type": "object", "properties": {}}),
            server_label=server_label,
        )


# ── Transport interface ──────────────────────────────────────────────────────

class MCPTransport(ABC):
    @abstractmethod
    async def send(self, message: bytes) -> None: ...

    @abstractmethod
    async def recv(self) -> str: ...

    @abstractmethod
    async def close(self) -> None: ...


class StdioTransport(MCPTransport):
    """Runs an MCP server as a subprocess and communicates over its stdin/stdout."""

    def __init__(self, cmd: str, *args: str, env: dict[str, str] | None = None):
        self._cmd = cmd
        self._args = args
        self._env = env
        self._proc: asyncio.subprocess.Process | None = None

    async def start(self) -> None:
        self._proc = await asyncio.create_subprocess_exec(
            self._cmd,
            *self._args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            env=self._env,
        )

    async def send(self, message: bytes) -> None:
        assert self._proc and self._proc.stdin
        self._proc.stdin.write(message)
        await self._proc.stdin.drain()

    async def recv(self) -> str:
        assert self._proc and self._proc.stdout
        line = await self._proc.stdout.readline()
        return line.decode()

    async def close(self) -> None:
        if self._proc:
            try:
                self._proc.stdin.close()  # type: ignore[union-attr]
                await self._proc.wait()
            except Exception:
                self._proc.kill()


class HttpTransport(MCPTransport):
    """Communicates with a remote MCP server over HTTP POST (JSON-RPC)."""

    def __init__(self, base_url: str, headers: dict[str, str] | None = None):
        import httpx
        self._base_url = base_url.rstrip("/")
        self._headers = {"Content-Type": "application/json", **(headers or {})}
        self._client = httpx.AsyncClient(timeout=30.0)
        self._response_queue: asyncio.Queue[str] = asyncio.Queue()

    async def start(self) -> None:
        pass  # HTTP client is already ready

    async def send(self, message: bytes) -> None:
        url = f"{self._base_url}/mcp"
        resp = await self._client.post(url, content=message, headers=self._headers)
        resp.raise_for_status()
        await self._response_queue.put(resp.text)

    async def recv(self) -> str:
        return await self._response_queue.get()

    async def close(self) -> None:
        await self._client.aclose()


# ── High-level MCP client ────────────────────────────────────────────────────

class MCPClient:
    """Async MCP client. Use as an async context manager.

    Examples:
        async with MCPClient.stdio("npx", "-y", "@modelcontextprotocol/server-filesystem", "/tmp") as c:
            tools = await c.list_tools()

        async with MCPClient.http("http://localhost:3001") as c:
            result = await c.call_tool("search", {"query": "hello"})
    """

    _PROTOCOL_VERSION = "2024-11-05"

    def __init__(self, transport: MCPTransport, label: str = ""):
        self._transport = transport
        self._label = label
        self._id_counter = 0
        self._initialized = False

    # ── Factory methods ──────────────────────────────────────────────────────

    @classmethod
    def stdio(cls, cmd: str, *args: str, label: str = "", env: dict[str, str] | None = None) -> "MCPClient":
        """Create a client that spawns a local MCP server process.

        Example:
            MCPClient.stdio("npx", "-y", "@modelcontextprotocol/server-filesystem", "/workspace")
        """
        return cls(StdioTransport(cmd, *args, env=env), label=label or cmd)

    @classmethod
    def http(cls, base_url: str, label: str = "", headers: dict[str, str] | None = None) -> "MCPClient":
        """Create a client that connects to a remote MCP server over HTTP.

        Example:
            MCPClient.http("http://localhost:3001", label="my-skill-server")
        """
        return cls(HttpTransport(base_url, headers=headers), label=label or base_url)

    # ── Context manager ──────────────────────────────────────────────────────

    async def __aenter__(self) -> "MCPClient":
        await self._transport.start()
        await self._initialize()
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self._transport.close()

    # ── Protocol ─────────────────────────────────────────────────────────────

    def _next_id(self) -> int:
        self._id_counter += 1
        return self._id_counter

    async def _rpc(self, method: str, params: dict[str, Any] | None = None) -> Any:
        rid = self._next_id()
        await self._transport.send(_make_request(rid, method, params))
        raw = await self._transport.recv()
        if not raw.strip():
            return None
        response = _parse_response(raw)
        if "error" in response:
            err = response["error"]
            raise RuntimeError(f"MCP error [{err.get('code')}]: {err.get('message')}")
        return response.get("result")

    async def _initialize(self) -> None:
        if self._initialized:
            return
        await self._rpc(
            "initialize",
            params={
                "protocolVersion": self._PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "clientInfo": {"name": "attractor", "version": "0.1.0"},
            },
        )
        # Send initialized notification (no response expected)
        notif = json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n"
        await self._transport.send(notif.encode())
        self._initialized = True

    # ── Public API ────────────────────────────────────────────────────────────

    async def list_tools(self) -> list[MCPTool]:
        """Discover all tools this MCP server exposes."""
        result = await self._rpc("tools/list", params={})
        raw_tools: list[dict[str, Any]] = (result or {}).get("tools", [])
        return [MCPTool.from_mcp_dict(t, server_label=self._label) for t in raw_tools]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """Call a tool by name and return its result as a string."""
        result = await self._rpc("tools/call", params={"name": name, "arguments": arguments})
        if result is None:
            return ""
        # MCP returns content as a list of typed parts
        content = result.get("content", [])
        is_error = result.get("isError", False)
        parts: list[str] = []
        for part in content:
            if isinstance(part, dict):
                if part.get("type") == "text":
                    parts.append(part.get("text", ""))
                elif part.get("type") == "image":
                    parts.append(f"[image: {part.get('url', 'data')}]")
                else:
                    parts.append(str(part))
            else:
                parts.append(str(part))
        text = "\n".join(parts)
        if is_error:
            raise RuntimeError(f"MCP tool '{name}' returned an error: {text}")
        return text

    @property
    def label(self) -> str:
        return self._label
