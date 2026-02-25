"""MCP (Model Context Protocol) manager — sync wrapper around async MCP SDK.

Connects to MCP servers as stdio subprocesses, caches their tool definitions
in OpenAI function-calling format, and routes call_tool() to the right server.
Thread-safe: uses a persistent asyncio event loop on a daemon thread.
"""

import asyncio
import json
import logging
import threading
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

log = logging.getLogger(__name__)


class _ServerHandle:
    """Bookkeeping for one connected MCP server."""
    __slots__ = ("name", "params", "session", "_stdio_cm", "_session_cm")

    def __init__(self, name: str, params: StdioServerParameters):
        self.name = name
        self.params = params
        self.session: ClientSession | None = None
        self._stdio_cm: Any = None
        self._session_cm: Any = None


class MCPManager:
    """Manages MCP server connections and exposes tools in OpenAI format.

    Parameters
    ----------
    server_configs : dict
        Mapping of server name to config dict with keys:
        ``command`` (str), ``args`` (list[str]), ``env`` (dict, optional).
    """

    def __init__(self, server_configs: dict):
        self._configs = server_configs
        self._handles: list[_ServerHandle] = []
        # tool name -> server handle, for routing call_tool()
        self._tool_map: dict[str, _ServerHandle] = {}
        # Cached OpenAI-format tool definitions
        self._openai_tools: list[dict] = []

        # Persistent event loop on a daemon thread
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._thread.start()

    # ── Public sync API ──────────────────────────────────────────────────

    def connect(self) -> None:
        """Connect to all configured MCP servers and cache tools."""
        self._run(self._connect_all())

    def get_openai_tools(self) -> list[dict]:
        """Return tool definitions in OpenAI function-calling format."""
        return self._openai_tools

    def call_tool(self, name: str, arguments: dict) -> str:
        """Call an MCP tool by name. Returns result text."""
        handle = self._tool_map.get(name)
        if not handle:
            return f"[mcp] Unknown tool: {name}"
        return self._run(self._call_tool(handle, name, arguments))

    def disconnect(self) -> None:
        """Disconnect all MCP servers."""
        self._run(self._disconnect_all())

    def shutdown(self) -> None:
        """Disconnect servers and stop the event loop thread."""
        try:
            self.disconnect()
        except Exception:
            pass
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=5)

    # ── Sync/async bridge ────────────────────────────────────────────────

    def _run(self, coro):
        """Submit a coroutine to the persistent loop and block for result."""
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=30)

    # ── Async internals ──────────────────────────────────────────────────

    async def _connect_all(self) -> None:
        for name, cfg in self._configs.items():
            try:
                await self._connect_one(name, cfg)
            except Exception as exc:
                log.error("[mcp] Failed to connect to %s: %s", name, exc)

    async def _connect_one(self, name: str, cfg: dict) -> None:
        params = StdioServerParameters(
            command=cfg["command"],
            args=cfg.get("args", []),
            env=cfg.get("env"),
        )
        handle = _ServerHandle(name, params)

        # Enter stdio_client context manager manually (keeps subprocess alive)
        handle._stdio_cm = stdio_client(params)
        read_stream, write_stream = await handle._stdio_cm.__aenter__()

        # Enter ClientSession context manager manually (keeps session alive)
        handle._session_cm = ClientSession(read_stream, write_stream)
        handle.session = await handle._session_cm.__aenter__()

        await handle.session.initialize()

        # Cache tools from this server
        result = await handle.session.list_tools()
        for tool in result.tools:
            self._tool_map[tool.name] = handle
            self._openai_tools.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": tool.inputSchema,
                },
            })

        self._handles.append(handle)
        log.info("[mcp] Connected to %s (%d tools)", name, len(result.tools))

    async def _call_tool(self, handle: _ServerHandle, name: str, arguments: dict) -> str:
        result = await handle.session.call_tool(name, arguments)
        # MCP returns a list of content blocks; join their text
        parts = []
        for block in result.content:
            if hasattr(block, "text"):
                parts.append(block.text)
            else:
                parts.append(str(block))
        return "\n".join(parts)

    async def _disconnect_all(self) -> None:
        for handle in reversed(self._handles):
            try:
                if handle._session_cm:
                    await handle._session_cm.__aexit__(None, None, None)
                if handle._stdio_cm:
                    await handle._stdio_cm.__aexit__(None, None, None)
            except Exception as exc:
                log.warning("[mcp] Error disconnecting %s: %s", handle.name, exc)
        self._handles.clear()
        self._tool_map.clear()
        self._openai_tools.clear()
