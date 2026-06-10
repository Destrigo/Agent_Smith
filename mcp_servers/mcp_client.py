import asyncio
from typing import Any, Callable, Dict, Optional


class MCPClient:

    def __init__(self) -> None:
        self._tools: Dict[str, dict[str, Any]] = {}
        self._loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()
        self._session: Any = None
        self._transport_ctx: Any = None
        self._session_ctx: Any = None

    def connect_stdio(self, command: str, args: Optional[list[str]] = None) -> None:
        self._loop.run_until_complete(
            self._connect_stdio(command, args or [])
        )

    def connect_http(self, url: str) -> None:
        from urllib.parse import urlparse, urlunparse
        parsed = urlparse(url)
        if parsed.path in ("", "/"):
            url = urlunparse(parsed._replace(path="/mcp"))
        self._loop.run_until_complete(self._connect_http(url))

    async def _connect_stdio(self, command: str, args: list[str]) -> None:
        import os
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

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

    def discover_tools(self) -> Dict[str, dict[str, Any]]:
        return dict(self._tools)

    def make_tool_wrappers(self) -> Dict[str, Callable[..., Any]]:
        wrappers: Dict[str, Callable[..., Any]] = {}
        for name, schema in self._tools.items():
            def _make(tool_name: str, doc: str,
                      input_schema: dict[str, Any]) -> Callable[..., Any]:
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

    def call_tool(self, tool_name: str, **kwargs: Any) -> Any:
        if tool_name not in self._tools:
            raise ValueError(
                f"Unknown MCP tool: '{tool_name}'. "
                f"Available: {list(self._tools)}"
            )
        return self._loop.run_until_complete(
            self._call_tool_async(tool_name, kwargs)
        )

    async def _call_tool_async(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        result = await self._session.call_tool(tool_name, arguments=arguments)
        if not result.content:
            return None
        # return raw text, not parsed JSON — callers decide; multiple items joined so result is always a string
        texts = [getattr(c, "text", str(c)) for c in result.content]
        return texts[0] if len(texts) == 1 else "\n".join(texts)

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
