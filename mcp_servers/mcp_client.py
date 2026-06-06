"""
MCPClient — synchronous bridge between the sandbox and an external MCP server.

Supports two transports:
    stdio           Connect to an MCP server launched as a subprocess.
    streamable-http Connect to an MCP server listening on an HTTP URL.

The client discovers tools automatically after connecting and exposes them as
plain Python callables that can be injected into the sandbox namespace.
"""

import asyncio
from typing import Any, Callable, Dict, Optional


class MCPClient:

    def __init__(self) -> None:
        self._tools: Dict[str, dict] = {}
        self._loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()
        self._session: Any = None
        # Keep context-manager objects alive for the session lifetime.
        self._transport_ctx: Any = None
        self._session_ctx: Any = None

    # Public connect API (sync wrappers)
    def connect_stdio(self, command: str, args: Optional[list] = None) -> None:
        """Launch *command* as a subprocess and connect via stdio transport."""
        self._loop.run_until_complete(
            self._connect_stdio(command, args or [])
        )

    def connect_http(self, url: str) -> None:
        """Connect to an MCP server via streamable-HTTP at *url*.

        FastMCP's streamable-HTTP transport mounts at /mcp by default.
        If *url* has no path (or just "/"), /mcp is appended automatically
        so that both http://localhost:8000 and http://localhost:8000/mcp work.
        """
        from urllib.parse import urlparse, urlunparse
        parsed = urlparse(url)
        if parsed.path in ("", "/"):
            url = urlunparse(parsed._replace(path="/mcp"))
        self._loop.run_until_complete(self._connect_http(url))

    # Async connect internals
    async def _connect_stdio(self, command: str, args: list) -> None:
        import os
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        # Pass current environment so the subprocess inherits vars like
        # TESTBED_PATH, SANDBOX_TEST_CODE, OPENROUTER_API_KEY, etc.
        params = StdioServerParameters(command=command, args=args,
                                       env=os.environ.copy())
        self._transport_ctx = stdio_client(params)
        read_stream, write_stream = await self._transport_ctx.__aenter__()

        self._session_ctx = ClientSession(read_stream, write_stream)
        self._session = await self._session_ctx.__aenter__()
        await self._session.initialize()

        await self._load_tools()

    async def _connect_http(self, url: str) -> None:
        from mcp import ClientSession
        from mcp.client.streamable_http import streamable_http_client

        self._transport_ctx = streamable_http_client(url)
        try:
            read_stream, write_stream, _ = await self._transport_ctx.__aenter__()

            self._session_ctx = ClientSession(read_stream, write_stream)
            self._session = await self._session_ctx.__aenter__()
            await self._session.initialize()
        except asyncio.CancelledError as exc:
            raise ConnectionError(
                f"MCP handshake with {url} was cancelled — "
                "is the server running and does it speak the MCP streamable-HTTP protocol?"
            ) from exc

        await self._load_tools()

    async def _load_tools(self) -> None:
        result = await self._session.list_tools()
        for tool in result.tools:
            self._tools[tool.name] = {
                "name": tool.name,
                "description": tool.description or "",
                "inputSchema": tool.inputSchema or {},
            }

    # Tool discovery
    def discover_tools(self) -> Dict[str, dict]:
        """Return the schema dict for all discovered tools."""
        return dict(self._tools)

    def make_tool_wrappers(self) -> Dict[str, Callable]:
        """
        Return a dict of {name: callable} for every discovered tool.

        Each callable has the tool's description as its docstring and accepts
        keyword arguments that are forwarded to the MCP server.
        """
        wrappers: Dict[str, Callable] = {}
        for name, schema in self._tools.items():
            def _make(tool_name: str, doc: str,
                      input_schema: dict) -> Callable:
                # Build ordered list of parameter names from the JSON schema
                # so positional calls like run_tests(code) work correctly.
                props = input_schema.get("properties", {})
                required = input_schema.get("required", [])
                param_names = list(required) + [
                    k for k in props if k not in required
                ]

                def wrapper(*args: Any, **kwargs: Any) -> Any:
                    for i, arg in enumerate(args):
                        if i < len(param_names):
                            kwargs[param_names[i]] = arg
                    return self.call_tool(tool_name, **kwargs)
                wrapper.__name__ = tool_name
                wrapper.__doc__ = doc
                return wrapper
            wrappers[name] = _make(
                name,
                schema.get("description", ""),
                schema.get("inputSchema", {}),
            )
        return wrappers

    # Tool invocation (sync)
    def call_tool(self, tool_name: str, **kwargs: Any) -> Any:
        """Call a remote MCP tool synchronously."""
        if tool_name not in self._tools:
            raise ValueError(
                f"Unknown MCP tool: '{tool_name}'. "
                f"Available: {list(self._tools)}"
            )
        return self._loop.run_until_complete(
            self._call_tool_async(tool_name, kwargs)
        )

    async def _call_tool_async(self, tool_name: str, arguments: dict) -> Any:
        result = await self._session.call_tool(tool_name, arguments=arguments)
        if not result.content:
            return None
        # Return raw text — callers decide whether to parse as JSON.
        # Auto-parsing here would cause double-decode for tools that
        # deliberately return a JSON string (e.g. run_tests).
        # Multiple content items are joined with newlines so the result is
        # always a string, enabling substring checks like "foo" in result.
        texts = [getattr(c, "text", str(c)) for c in result.content]
        return texts[0] if len(texts) == 1 else "\n".join(texts)

    # Cleanup
    def close(self) -> None:
        async def _close() -> None:
            if self._session_ctx is not None:
                await self._session_ctx.__aexit__(None, None, None)
            if self._transport_ctx is not None:
                await self._transport_ctx.__aexit__(None, None, None)

        try:
            self._loop.run_until_complete(_close())
        finally:
            self._loop.close()
